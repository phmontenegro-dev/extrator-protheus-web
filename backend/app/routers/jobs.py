"""
Endpoints de jobs assíncronos (Etapa 11).

    POST /jobs/relatorios/{id}/extrair-async          → enfileira
    POST /jobs/relatorio-livre/extrair-async          → enfileira
    POST /jobs/sql-livre/executar-async               → enfileira
    GET  /jobs                                         → lista jobs do usuário
    GET  /jobs/{id}                                    → status/progresso
    GET  /jobs/{id}/download                           → baixa CSV se concluido
    DELETE /jobs/{id}                                  → cancela se pendente

Admin vê jobs de qualquer usuário via /jobs?todos=true e pode ler/cancelar
qualquer job pelo id.

As rotas -async *não substituem* as síncronas — a Etapa 11 é adição. Front
decide qual usar por relatório.
"""
import os
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.auth.dependencies import get_usuario_atual
from app.database import get_db
from app.jobs import executor as job_executor
from app.jobs.eta import calcular_mediana_duracao_s
from app.jobs.runners import (
    runner_codigo_sql,
    runner_relatorio_livre,
    runner_relatorio_pronto,
)
from app.models.job import (
    STATUS_CONCLUIDO,
    STATUS_FINAIS,
    TIPO_CODIGO_SQL,
    TIPO_RELATORIO_LIVRE,
    TIPO_RELATORIO_PRONTO,
    JobExtracao,
)
from app.models.usuario import Usuario
from app.relatorios_prontos.registry import buscar as buscar_relatorio
from app.schemas.jobs import JobCriadoResponse, JobResumo
from app.schemas.relatorio_livre import FiltrosLivre
from app.schemas.relatorios import FiltrosFilialPeriodo, FiltrosPeriodo
from app.schemas.sql_livre import SqlDownloadPayload
from app.config import get_settings
from app.utils import logs
from app.utils.permissoes import pode_acessar
from app.utils.sql_validator import SqlInvalidoError, validar_sql


router = APIRouter(prefix="/jobs", tags=["jobs"])


# =============================================================================
# Helpers
# =============================================================================

def _checar_limite(db: Session, usuario: Usuario) -> None:
    """Rejeita com 429 se o usuário já tem jobs demais ativos."""
    limite = get_settings().jobs_max_por_usuario
    ativos = job_executor.contar_jobs_ativos_do_usuario(db, usuario.id)
    if ativos >= limite:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Você já tem {ativos} job(s) em andamento. Aguarde a conclusão "
                f"ou cancele um pendente antes de criar outro."
            ),
        )


def _criar_e_submeter(
    *,
    db: Session,
    request: Request,
    usuario: Usuario,
    tipo: str,
    relatorio_id: str,
    titulo: str,
    nome_arquivo: str,
    filtros_json: Optional[dict] = None,
    sql_texto: Optional[str] = None,
    runner,
    acao_log: str,
) -> JobExtracao:
    """
    Cria a linha de JobExtracao, calcula ETA, envia pro executor, loga
    criação do job, retorna o objeto JobExtracao.
    """
    job_id = str(uuid.uuid4())
    eta = calcular_mediana_duracao_s(db, relatorio_id)

    job = JobExtracao(
        id=job_id,
        usuario_id=usuario.id,
        username=usuario.username,
        tipo=tipo,
        relatorio_id=relatorio_id,
        titulo=titulo[:300],
        filtros_json=filtros_json,
        sql_texto=sql_texto,
        nome_arquivo=nome_arquivo,
        duracao_estimada_s=eta,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Log de criação — a extração em si vai gerar outro log quando terminar.
    logs.registrar(
        db, acao=acao_log, request=request,
        usuario_id=usuario.id, username=usuario.username,
        relatorio_id=relatorio_id,
        parametros={"job_id": job_id, "assincrono": True, **(filtros_json or {})},
        sucesso=True,
    )

    job_executor.submeter(job_id, runner)
    return job


# =============================================================================
# POST /jobs/relatorios/{id}/extrair-async
# =============================================================================

class _PayloadNenhum(BaseModel):
    """Corpo vazio aceito pros relatórios sem filtros."""


def _montar_filtros_dict_e_titulo(
    relatorio_id: str, payload: dict
) -> tuple[dict, str, str]:
    """
    A partir do id e do payload cru, devolve (filtros_pra_runner, titulo, nome_arquivo).

    Faz a validação via Pydantic reusando os schemas existentes.
    """
    info = buscar_relatorio(relatorio_id)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Relatório '{relatorio_id}' não existe.",
        )
    nome_rel = info["nome"].split(" — ")[0]  # "CT2010" de "CT2010 — Lançamentos ..."

    if info["filtros"] == "periodo":
        f = FiltrosPeriodo(**payload)
        di, df = f.para_aaaammdd()
        filtros = {"data_inicio": di, "data_fim": df}
        titulo = f"{nome_rel} — {di} a {df}"
        nome_arquivo = f"{relatorio_id.upper()}_{di}_a_{df}.csv"
    elif info["filtros"] == "filial_periodo":
        f = FiltrosFilialPeriodo(**payload)
        di, df = f.para_aaaammdd()
        fil = f.filial.strip()
        filtros = {"filial": fil, "data_inicio": di, "data_fim": df}
        titulo = f"{nome_rel} — filial {fil}, {di} a {df}"
        nome_arquivo = f"{relatorio_id.upper()}_{fil}_{di}_a_{df}.csv"
    elif info["filtros"] == "nenhum":
        _PayloadNenhum(**payload)
        filtros = {}
        titulo = nome_rel
        nome_arquivo = f"{relatorio_id.upper()}.csv"
    else:
        # Para "livre" / "sql" existe endpoint dedicado.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Use o endpoint específico de /jobs para este tipo ({info['filtros']}).",
        )
    return filtros, titulo, nome_arquivo


@router.post("/relatorios/{relatorio_id}/extrair-async", response_model=JobCriadoResponse)
def extrair_relatorio_async(
    relatorio_id: str,
    payload: dict,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> JobCriadoResponse:
    """
    Enfileira a extração de um relatório pronto em background.

    Aceita o mesmo payload do endpoint síncrono correspondente — o tipo é
    inferido do `filtros` registrado em registry.py.
    """
    if not pode_acessar(db, usuario, relatorio_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para este relatório.",
        )
    _checar_limite(db, usuario)

    filtros, titulo, nome_arq = _montar_filtros_dict_e_titulo(relatorio_id, payload)
    runner = runner_relatorio_pronto(relatorio_id, filtros, nome_arq)

    job = _criar_e_submeter(
        db=db, request=request, usuario=usuario,
        tipo=TIPO_RELATORIO_PRONTO,
        relatorio_id=relatorio_id,
        titulo=titulo,
        nome_arquivo=nome_arq,
        filtros_json=filtros,
        runner=runner,
        acao_log="job_criado",
    )
    return JobCriadoResponse(
        job_id=job.id, status=job.status,
        mensagem="Job enfileirado. Acompanhe em /jobs.",
    )


# =============================================================================
# POST /jobs/relatorio-livre/extrair-async
# =============================================================================

@router.post("/relatorio-livre/extrair-async", response_model=JobCriadoResponse)
def extrair_livre_async(
    filtros: FiltrosLivre,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> JobCriadoResponse:
    if not pode_acessar(db, usuario, "relatorio_livre"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para o Relatório Livre.",
        )
    _checar_limite(db, usuario)

    tabela = filtros.tabela.upper()
    di, df = filtros.datas_aaaammdd()
    if di and df:
        titulo = f"Livre {tabela} — {di} a {df}"
        nome_arq = f"Livre_{tabela}_{di}_a_{df}.csv"
    else:
        titulo = f"Livre {tabela}"
        nome_arq = f"Livre_{tabela}.csv"

    filtros_dict = {
        "tabela": tabela,
        "colunas": filtros.colunas,
        "campo_data": filtros.campo_data,
        "data_inicio": di,
        "data_fim": df,
        "max_linhas": filtros.max_linhas,
    }
    runner = runner_relatorio_livre(filtros_dict, nome_arq)

    job = _criar_e_submeter(
        db=db, request=request, usuario=usuario,
        tipo=TIPO_RELATORIO_LIVRE,
        relatorio_id="relatorio_livre",
        titulo=titulo,
        nome_arquivo=nome_arq,
        filtros_json=filtros_dict,
        runner=runner,
        acao_log="job_criado",
    )
    return JobCriadoResponse(
        job_id=job.id, status=job.status,
        mensagem="Job enfileirado. Acompanhe em /jobs.",
    )


# =============================================================================
# POST /jobs/sql-livre/executar-async
# =============================================================================

@router.post("/sql-livre/executar-async", response_model=JobCriadoResponse)
def executar_sql_async(
    payload: SqlDownloadPayload,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> JobCriadoResponse:
    """
    Executa SELECT em background e deixa o CSV pronto pra download.

    Validação de SQL é idêntica à síncrona (SELECT/WITH only, bloqueios
    defensivos, múltiplas sentenças rejeitadas).
    """
    if not pode_acessar(db, usuario, "codigo_sql"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para executar SQL livre.",
        )
    _checar_limite(db, usuario)

    try:
        sql_limpo = validar_sql(payload.sql)
    except SqlInvalidoError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))

    nome_arq = (payload.nome_arquivo or "consulta_sql").strip()
    if not nome_arq.lower().endswith(".csv"):
        nome_arq += ".csv"

    # Pra código SQL o timeout é o da tela síncrona (4 min). Pra jobs grandes
    # reaproveita o ORACLE_QUERY_TIMEOUT_S.
    timeout_s = get_settings().oracle_query_timeout_s
    runner = runner_codigo_sql(sql_limpo, nome_arq, timeout_s)

    job = _criar_e_submeter(
        db=db, request=request, usuario=usuario,
        tipo=TIPO_CODIGO_SQL,
        relatorio_id="codigo_sql",
        titulo=f"SQL — {nome_arq}",
        nome_arquivo=nome_arq,
        sql_texto=sql_limpo,
        filtros_json={"nome_arquivo": nome_arq},
        runner=runner,
        acao_log="job_criado",
    )
    return JobCriadoResponse(
        job_id=job.id, status=job.status,
        mensagem="Job enfileirado. Acompanhe em /jobs.",
    )


# =============================================================================
# GET /jobs — lista jobs do usuário
# =============================================================================

@router.get("", response_model=list[JobResumo])
def listar_jobs(
    todos: bool = Query(
        False,
        description="Admin only. Retorna jobs de todos os usuários.",
    ),
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> list[JobResumo]:
    """
    Lista jobs do usuário (ou todos, se admin + ?todos=true).

    Ordenação: mais recentes primeiro. Inclui ativos + finalizados dentro
    da retenção.
    """
    # IMPORTANTE: SQLAlchemy exige que .filter() venha ANTES de .limit() —
    # chamar filter em query já limitada dispara InvalidRequestError.
    q = db.query(JobExtracao)
    if todos:
        if not usuario.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Só admins podem ver jobs de outros usuários.",
            )
    else:
        q = q.filter(JobExtracao.usuario_id == usuario.id)

    rows = q.order_by(desc(JobExtracao.criado_em)).limit(limite).all()
    return [JobResumo.model_validate(j) for j in rows]


# =============================================================================
# GET /jobs/{id}
# =============================================================================

def _buscar_job(db: Session, usuario: Usuario, job_id: str) -> JobExtracao:
    job = db.get(JobExtracao, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.")
    # Não-admin só vê os próprios.
    if not usuario.is_admin and job.usuario_id != usuario.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job não encontrado.")
    return job


@router.get("/{job_id}", response_model=JobResumo)
def obter_job(
    job_id: str,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> JobResumo:
    """Detalhes de 1 job (polling do frontend)."""
    job = _buscar_job(db, usuario, job_id)
    return JobResumo.model_validate(job)


# =============================================================================
# GET /jobs/{id}/download
# =============================================================================

@router.get("/{job_id}/download")
def baixar_job(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> FileResponse:
    """Baixa o CSV de um job concluído."""
    job = _buscar_job(db, usuario, job_id)
    if job.status != STATUS_CONCLUIDO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job não está concluído (status={job.status}).",
        )
    if not job.caminho_csv or not os.path.exists(job.caminho_csv):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Arquivo expirado ou não encontrado. Rode a extração de novo.",
        )

    logs.registrar(
        db, acao="job_download", request=request,
        usuario_id=usuario.id, username=usuario.username,
        relatorio_id=job.relatorio_id,
        parametros={"job_id": job.id, "nome_arquivo": job.nome_arquivo},
        sucesso=True,
    )

    return FileResponse(
        path=job.caminho_csv,
        media_type="text/csv; charset=utf-8",
        filename=job.nome_arquivo or f"{job_id}.csv",
        headers={"Access-Control-Expose-Headers": "Content-Disposition"},
    )


# =============================================================================
# DELETE /jobs/{id}
# =============================================================================

@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancelar_job(
    job_id: str,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> None:
    """
    Cancela um job. Só funciona enquanto o status for `pendente` (ainda na
    fila). Depois que entra em `conectando` não dá pra cancelar — ThreadPool
    e oracledb não suportam interrupção cooperativa segura.
    """
    job = _buscar_job(db, usuario, job_id)
    if job.status in STATUS_FINAIS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Job já está em estado final ({job.status}).",
        )
    cancelado = job_executor.cancelar(db, job_id)
    if not cancelado:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job já saiu da fila e está em execução; não é possível cancelar.",
        )
    logs.registrar(
        db, acao="job_cancelado", request=request,
        usuario_id=usuario.id, username=usuario.username,
        relatorio_id=job.relatorio_id,
        parametros={"job_id": job_id},
        sucesso=True,
    )
