"""
Scheduler de agendamentos — processo standalone.

Executado via systemd em produção (unit `extrator-scheduler.service`):
  - Roda em loop infinito
  - A cada 60s, abre sessão, varre Agendamentos ativos com
    proxima_execucao <= now_utc(), dispara via dispatcher
  - Atualiza `ultima_execucao` e `proxima_execucao`
  - Dorme e repete

Também sincroniza o status de AgendamentoExecucao a partir do JobExtracao
correspondente: quando o job termina, propaga pro campo da execução.

Separado do uvicorn por 2 motivos:
  1. Uvicorn tem 4 workers → não dá pra deixar 4 schedulers rodando, cada
     disparando os mesmos agendamentos.
  2. Mais fácil de operar: `systemctl restart extrator-scheduler` sem mexer
     na API.
"""
from __future__ import annotations

import logging
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Suporta rodar como "python scripts/scheduler.py".
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.agendamentos.dispatcher import disparar_agendamento  # noqa: E402
from app.agendamentos.schedule import calcular_proxima_execucao  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.jobs.executor import iniciar_executor  # noqa: E402
from app.jobs.watchdog import marcar_zumbis_agora  # noqa: E402
from app.models.agendamento import (  # noqa: E402
    EXEC_CONCLUIDA,
    EXEC_ERRO,
    EXEC_PENDENTE,
    Agendamento,
    AgendamentoExecucao,
)
from app.models.job import (  # noqa: E402
    STATUS_CONCLUIDO,
    STATUS_ERRO,
    JobExtracao,
)


INTERVALO_LOOP_S = 60

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("scheduler")


_parar = False


def _sinal_parar(signum, _frame):
    """Handler de SIGTERM/SIGINT — sai no fim do tick atual."""
    global _parar
    log.info("recebido sinal %s — parando após o tick atual", signum)
    _parar = True


def _calcular_proxima_se_null() -> None:
    """
    Pra qualquer agendamento ativo com `proxima_execucao` NULL, calcula agora.
    Acontece na primeira vez que o scheduler vê um agendamento novo.
    """
    db = SessionLocal()
    try:
        candidatos = (
            db.query(Agendamento)
            .filter(
                Agendamento.ativo.is_(True),
                Agendamento.proxima_execucao.is_(None),
            )
            .all()
        )
        if not candidatos:
            return
        for ag in candidatos:
            ag.proxima_execucao = calcular_proxima_execucao(ag)
        db.commit()
        log.info("bootstrapped proxima_execucao de %d agendamento(s)", len(candidatos))
    finally:
        db.close()


def _disparar_vencidos() -> int:
    """
    Pega agendamentos ativos com proxima_execucao <= now e dispara.
    Retorna quantos disparou.
    """
    disparados = 0
    db = SessionLocal()
    try:
        agora = datetime.now(timezone.utc)
        vencidos = (
            db.query(Agendamento)
            .filter(
                Agendamento.ativo.is_(True),
                Agendamento.proxima_execucao.isnot(None),
                Agendamento.proxima_execucao <= agora,
            )
            .order_by(Agendamento.proxima_execucao.asc())
            .all()
        )
        for ag in vencidos:
            try:
                disparar_agendamento(db, ag)
                disparados += 1
            except Exception:
                # dispatcher já faz best effort pra marcar erro, mas protegemos
                # o loop de qualquer exceção não prevista.
                log.exception("erro inesperado ao disparar agendamento %s", ag.id)
    finally:
        db.close()
    return disparados


def _rodar_watchdog() -> int:
    """
    Marca jobs zumbis (sem heartbeat por >60s) como erro. Isso cobre o caso
    do worker do uvicorn morrer em silêncio (segfault, kill, OOM user-space).
    Antes dessa correção, jobs ficavam em "tratando 95%" eternamente.
    """
    db = SessionLocal()
    try:
        return marcar_zumbis_agora(db)
    finally:
        db.close()


def _sincronizar_execucoes_pendentes() -> int:
    """
    Pra cada AgendamentoExecucao em status 'pendente' cujo job já terminou,
    propaga o status/total_linhas/erro. Isso acontece de forma assíncrona —
    o scheduler vê o resultado quando o job termina em outro thread.
    """
    atualizadas = 0
    db = SessionLocal()
    try:
        pendentes = (
            db.query(AgendamentoExecucao, JobExtracao)
            .join(JobExtracao, JobExtracao.id == AgendamentoExecucao.job_id)
            .filter(
                AgendamentoExecucao.status == EXEC_PENDENTE,
                JobExtracao.status.in_([STATUS_CONCLUIDO, STATUS_ERRO]),
            )
            .all()
        )
        for exec_, job in pendentes:
            if job.status == STATUS_CONCLUIDO:
                exec_.status = EXEC_CONCLUIDA
                exec_.total_linhas = job.total_linhas
                exec_.tamanho_bytes = job.tamanho_bytes
                exec_.nome_arquivo = job.nome_arquivo
                exec_.concluido_em = job.concluido_em or datetime.now(timezone.utc)
            else:
                exec_.status = EXEC_ERRO
                exec_.erro_mensagem = job.erro_mensagem or "Job terminou com erro."
                exec_.concluido_em = job.concluido_em or datetime.now(timezone.utc)
            atualizadas += 1
        if atualizadas:
            db.commit()
            log.info("%d execução(ões) sincronizada(s) a partir do job", atualizadas)
    finally:
        db.close()
    return atualizadas


def main() -> int:
    signal.signal(signal.SIGTERM, _sinal_parar)
    signal.signal(signal.SIGINT, _sinal_parar)

    # Mesmo executor de jobs que o uvicorn usa — como o scheduler roda em
    # processo separado, tem o SEU PRÓPRIO ThreadPool. Isso NÃO infringe
    # o limite JOBS_MAX_WORKERS=2 do uvicorn: é um pool a mais dedicado só
    # aos agendamentos. Tem 2 threads por padrão, então o scheduler pode
    # processar até 2 disparos simultâneos.
    iniciar_executor()

    log.info("scheduler iniciado (tick=%ds)", INTERVALO_LOOP_S)
    while not _parar:
        try:
            _calcular_proxima_se_null()
            n_disparados = _disparar_vencidos()
            n_sync = _sincronizar_execucoes_pendentes()
            n_zumbis = _rodar_watchdog()
            if n_disparados or n_sync or n_zumbis:
                log.info(
                    "tick: disparados=%d sincronizadas=%d zumbis=%d",
                    n_disparados, n_sync, n_zumbis,
                )
        except Exception:
            log.exception("erro no loop do scheduler (continuando)")

        # Sleep interruptível por SIGTERM.
        for _ in range(INTERVALO_LOOP_S):
            if _parar:
                break
            time.sleep(1)

    log.info("scheduler encerrado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
