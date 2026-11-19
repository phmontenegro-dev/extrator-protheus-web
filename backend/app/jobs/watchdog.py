"""
Watchdog de jobs zumbis.

Chamado pelo scheduler systemd a cada tick (60s). Marca como erro qualquer
job em status ativo cujo heartbeat está parado há muito tempo — o que indica
que o worker que estava processando morreu (segfault, kill, OOM silencioso).

Diferença do _marcar_zumbis() no limpar_jobs.py:
  - esse roda a cada 60s, não 3x/dia
  - usa heartbeat_em (sinal de vida real), não criado_em (que é imutável)
  - timeout muito mais apertado: 2 minutos sem heartbeat vs 4 horas sem nada

Quando aciona:
  - worker do uvicorn morre no meio de to_csv() grande → job vira erro em ~2min
  - processo kill -9 → mesmo efeito
  - deadlock/hang do oracledb sem exceção → heartbeat para, watchdog pega
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.job import STATUS_ATIVOS, STATUS_ERRO, JobExtracao

log = logging.getLogger(__name__)

# Se não há heartbeat há mais que isso, trata como zumbi.
# 2 minutos > 2s de tick da thread de progresso + 60s de ciclo do watchdog,
# com folga pra micro-contenções de IO/CPU que podem atrasar o heartbeat
# em até ~10s legitimamente.
HEARTBEAT_TIMEOUT_S = 120

# Pra jobs que nunca receberam heartbeat (status mudou mas a thread de progresso
# nem começou), damos um prazo maior — pode ser queue backlog do executor.
NUNCA_BATEU_TIMEOUT_S = 300


def marcar_zumbis_agora(db: Session) -> int:
    """
    Marca como erro todos os jobs ativos considerados zumbis no momento.
    Retorna a quantidade marcada.
    """
    agora = datetime.now(timezone.utc)
    limite_hb = agora - timedelta(seconds=HEARTBEAT_TIMEOUT_S)
    limite_sem_hb = agora - timedelta(seconds=NUNCA_BATEU_TIMEOUT_S)

    # Candidatos: ativos COM heartbeat velho, OU ativos sem heartbeat mas antigos.
    candidatos = (
        db.query(JobExtracao)
        .filter(JobExtracao.status.in_(STATUS_ATIVOS))
        .filter(
            # (heartbeat_em NOT NULL AND heartbeat_em < limite_hb)
            # OR (heartbeat_em IS NULL AND criado_em < limite_sem_hb)
            (
                (JobExtracao.heartbeat_em.isnot(None))
                & (JobExtracao.heartbeat_em < limite_hb)
            )
            | (
                (JobExtracao.heartbeat_em.is_(None))
                & (JobExtracao.criado_em < limite_sem_hb)
            )
        )
        .all()
    )

    if not candidatos:
        return 0

    def _idle(ref: datetime) -> int:
        # Postgres com tz devolve aware; SQLite devolve naive. Normaliza.
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        return int((agora - ref).total_seconds())

    for j in candidatos:
        if j.heartbeat_em:
            idle = _idle(j.heartbeat_em)
            motivo = (
                f"Worker interrompido inesperadamente — sem sinal de vida há "
                f"{idle}s (limite: {HEARTBEAT_TIMEOUT_S}s)."
            )
        else:
            idle = _idle(j.criado_em)
            motivo = (
                f"Job nunca começou a reportar progresso em {idle}s "
                f"(limite: {NUNCA_BATEU_TIMEOUT_S}s) — provável crash antes "
                f"do primeiro tick."
            )
        j.status = STATUS_ERRO
        j.erro_mensagem = motivo
        j.concluido_em = agora
        log.warning("watchdog marcou job %s como erro: %s", j.id, motivo)

    db.commit()
    return len(candidatos)
