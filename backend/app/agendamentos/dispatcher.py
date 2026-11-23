"""
Dispatcher: dado um Agendamento que chegou a hora, cria um JobExtracao via
executor + registra uma AgendamentoExecucao vinculada.

Rechecagem de permissão aqui (etapa H — Permissão na hora de rodar):
se o usuário dono do agendamento foi desativado ou perdeu a permissão do
relatório desde a criação, o dispatcher PAUSA o agendamento (ativo=False)
e grava uma execução de erro explicando o motivo.

Chamado a partir de:
  - scripts/scheduler.py (loop systemd, de 60 em 60s)
  - router de /agendamentos/{id}/testar (botão "Testar agora" na UI)
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.agendamentos.datas import calcular_datas_do_preset
from app.agendamentos.schedule import calcular_proxima_execucao
from app.jobs import executor as job_executor
from app.jobs.eta import calcular_mediana_duracao_s
from app.jobs.runners import (
    runner_codigo_sql,
    runner_relatorio_livre,
    runner_relatorio_pronto,
)
from app.models.agendamento import (
    EXEC_ERRO,
    EXEC_PENDENTE,
    Agendamento,
    AgendamentoExecucao,
)
from app.models.job import (
    TIPO_CODIGO_SQL,
    TIPO_RELATORIO_LIVRE,
    TIPO_RELATORIO_PRONTO,
    JobExtracao,
)
from app.models.usuario import Usuario
from app.relatorios_prontos.registry import buscar as buscar_relatorio
from app.utils.permissoes import pode_acessar
from app.utils.sql_validator import SqlInvalidoError, validar_sql

log = logging.getLogger(__name__)


def _nome_arquivo(ag: Agendamento, data_inicio: str | None, data_fim: str | None) -> str:
    """Nome do CSV salvo no servidor + usado no Content-Disposition do download."""
    from app.models.agendamento import NOME_SOBRESCREVER
    base = ag.relatorio_id.upper()
    if ag.estrategia_nome == NOME_SOBRESCREVER:
        return f"{base}.csv"
    # padrão: inclui as datas do período OU timestamp
    if data_inicio and data_fim:
        return f"{base}_{data_inicio}_a_{data_fim}.csv"
    agora = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return f"{base}_{agora}.csv"


def _registrar_erro(
    db: Session, ag: Agendamento, mensagem: str, *, pausar: bool = False
) -> AgendamentoExecucao:
    """Cria AgendamentoExecucao com status=erro. Opcionalmente pausa o agendamento."""
    exec_ = AgendamentoExecucao(
        agendamento_id=ag.id,
        status=EXEC_ERRO,
        erro_mensagem=mensagem[:2000],
        concluido_em=datetime.now(timezone.utc),
    )
    db.add(exec_)
    ag.ultima_execucao = datetime.now(timezone.utc)
    if pausar:
        ag.ativo = False
    else:
        ag.proxima_execucao = calcular_proxima_execucao(ag)
    db.commit()
    return exec_


def disparar_agendamento(
    db: Session, ag: Agendamento, *, teste: bool = False
) -> AgendamentoExecucao:
    """
    Dispara um agendamento: valida, resolve datas, cria job + execução.

    `teste=True` significa "o usuário clicou em Testar agora" — não atualiza
    ultima_execucao nem proxima_execucao, pra não mascarar o cronograma.

    Sempre retorna uma AgendamentoExecucao — mesmo em caso de erro, pra
    aparecer no histórico.
    """
    # 1) Checagem de usuário ativo + permissão.
    usuario = db.query(Usuario).filter(
        Usuario.id == ag.usuario_id, Usuario.ativo.is_(True)
    ).first()
    if usuario is None:
        log.warning("agendamento %s: dono desativado — pausando", ag.id)
        return _registrar_erro(
            db, ag, "Usuário dono do agendamento foi desativado.", pausar=True
        )
    if not pode_acessar(db, usuario, ag.relatorio_id):
        log.warning("agendamento %s: dono perdeu permissão — pausando", ag.id)
        return _registrar_erro(
            db, ag,
            f"Usuário {usuario.username!r} não tem mais permissão em {ag.relatorio_id!r}.",
            pausar=True,
        )

    # 2) Resolve datas do preset.
    data_inicio, data_fim = calcular_datas_do_preset(ag.preset_datas)
    base = dict(ag.filtros_base or {})
    if data_inicio and data_fim:
        base.setdefault("data_inicio", data_inicio)
        base.setdefault("data_fim", data_fim)

    # 3) Monta runner conforme tipo.
    nome_arq = _nome_arquivo(ag, data_inicio, data_fim)
    try:
        runner = _montar_runner(ag, base, nome_arq)
    except (SqlInvalidoError, ValueError, KeyError) as e:
        return _registrar_erro(db, ag, f"Configuração inválida: {e}")

    # 4) Cria o JobExtracao (reusa a infra da Etapa 11).
    job_id = str(uuid.uuid4())
    titulo = f"[Agendamento] {ag.nome}"
    eta = calcular_mediana_duracao_s(db, ag.relatorio_id)
    job = JobExtracao(
        id=job_id,
        usuario_id=usuario.id,
        username=usuario.username,
        tipo=ag.tipo,
        relatorio_id=ag.relatorio_id,
        titulo=titulo[:300],
        filtros_json=base,
        sql_texto=ag.sql_texto,
        nome_arquivo=nome_arq,
        duracao_estimada_s=eta,
    )
    db.add(job)
    # Flush explícito: o INSERT em agendamentos_execucoes tem FK pra
    # jobs_extracao.id. Sem o flush, o SQLAlchemy pode tentar inserir a
    # execução ANTES do job (porque usamos o id como string crua, sem
    # relationship()), e o Postgres rejeita com FK violation.
    db.flush()

    # 5) AgendamentoExecucao com params_resolvidos (snapshot do que rodou).
    exec_ = AgendamentoExecucao(
        agendamento_id=ag.id,
        job_id=job_id,
        status=EXEC_PENDENTE,
        params_resolvidos=base,
        nome_arquivo=nome_arq,
    )
    db.add(exec_)

    if not teste:
        ag.ultima_execucao = datetime.now(timezone.utc)
        ag.proxima_execucao = calcular_proxima_execucao(ag)

    db.commit()

    # 6) Enfileira no executor (fora do commit — se o submit falhar, o job já
    #    tá no banco e o próximo tick do scheduler pode re-submeter).
    try:
        job_executor.submeter(job_id, runner)
    except Exception as e:
        log.exception("falha ao submeter job do agendamento %s", ag.id)
        return _registrar_erro(db, ag, f"Falha ao enfileirar: {e}")

    log.info("agendamento %s disparado → job %s (teste=%s)", ag.id, job_id, teste)
    return exec_


def _montar_runner(ag: Agendamento, filtros: dict, nome_arq: str):
    """Retorna o runner (closure) adequado ao tipo do agendamento."""
    if ag.tipo == TIPO_RELATORIO_PRONTO:
        # Valida que o relatório ainda existe no registry (alguém removeu?)
        if buscar_relatorio(ag.relatorio_id) is None:
            raise ValueError(f"relatório {ag.relatorio_id!r} não existe mais")
        return runner_relatorio_pronto(ag.relatorio_id, filtros, nome_arq)

    if ag.tipo == TIPO_RELATORIO_LIVRE:
        # Formato idêntico ao do /jobs/relatorio-livre/extrair-async
        return runner_relatorio_livre(filtros, nome_arq)

    if ag.tipo == TIPO_CODIGO_SQL:
        if not ag.sql_texto:
            raise ValueError("agendamento de código SQL sem sql_texto")
        sql_limpo = validar_sql(ag.sql_texto)
        from app.config import get_settings
        return runner_codigo_sql(sql_limpo, nome_arq, get_settings().oracle_query_timeout_s)

    raise ValueError(f"tipo desconhecido: {ag.tipo!r}")
