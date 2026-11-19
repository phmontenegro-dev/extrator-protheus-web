"""
Endpoints de agendamentos (Etapa 14).

Autenticação:
  - endpoints de UI (CRUD, ver execuções, testar): cookie de sessão do usuário
  - endpoints consumidos pelo script sincronizador no PC: header
    `X-Agendamento-Token: sk_ag_<id>_<rand>` (hash bcrypt no banco)

Separamos as duas famílias em dois "sub-routers" pra não confundir deps.
"""
import os
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.agendamentos.dispatcher import disparar_agendamento
from app.agendamentos.gerador_script import gerar_para_so
from app.agendamentos.schedule import calcular_proxima_execucao
from app.agendamentos.token import extrair_id_do_token, gerar_token, token_bate
from app.auth.dependencies import get_usuario_atual
from app.database import get_db
from app.models.agendamento import (
    EXEC_CONCLUIDA,
    Agendamento,
    AgendamentoExecucao,
)
from app.models.usuario import Usuario
from app.schemas.agendamentos import (
    AgendamentoCriadoResponse,
    AgendamentoCriar,
    AgendamentoResumo,
    CallbackDownload,
    ExecucaoPendenteParaScript,
    ExecucaoResumo,
    ScriptGerado,
)
from app.utils import logs
from app.utils.permissoes import pode_acessar


router = APIRouter(prefix="/agendamentos", tags=["agendamentos"])


# =============================================================================
# Helper: busca agendamento dessa pessoa, ou 404
# =============================================================================

def _buscar_proprio(
    db: Session, usuario: Usuario, agendamento_id: int
) -> Agendamento:
    ag = db.get(Agendamento, agendamento_id)
    if ag is None:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    # Não-admin só vê os próprios.
    if not usuario.is_admin and ag.usuario_id != usuario.id:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    return ag


# =============================================================================
# CRUD — autenticação via cookie
# =============================================================================

@router.get("", response_model=list[AgendamentoResumo])
def listar(
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> list[AgendamentoResumo]:
    """Lista agendamentos do usuário (admin vê todos)."""
    q = db.query(Agendamento)
    if not usuario.is_admin:
        q = q.filter(Agendamento.usuario_id == usuario.id)
    rows = q.order_by(desc(Agendamento.criado_em)).all()
    return [AgendamentoResumo.model_validate(r) for r in rows]


@router.post("", response_model=AgendamentoCriadoResponse)
def criar(
    payload: AgendamentoCriar,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> AgendamentoCriadoResponse:
    """Cria um agendamento + gera token único mostrado UMA vez."""
    if not pode_acessar(db, usuario, payload.relatorio_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para esse relatório.",
        )

    ag = Agendamento(
        usuario_id=usuario.id,
        username=usuario.username,
        nome=payload.nome,
        descricao=payload.descricao,
        tipo=payload.tipo,
        relatorio_id=payload.relatorio_id,
        filtros_base=payload.filtros_base,
        sql_texto=payload.sql_texto,
        preset_datas=payload.preset_datas,
        frequencia=payload.frequencia,
        dias_semana=payload.dias_semana,
        dia_mes=payload.dia_mes,
        hora=payload.hora,
        minuto=payload.minuto,
        ativo=payload.ativo,
        estrategia_nome=payload.estrategia_nome,
        retencao_dias=payload.retencao_dias,
    )
    db.add(ag)
    db.flush()   # pra ter id antes do token
    token_claro, token_hash, token_prefixo = gerar_token(ag.id)
    ag.token_hash = token_hash
    ag.token_prefixo = token_prefixo
    ag.proxima_execucao = calcular_proxima_execucao(ag)
    db.commit()
    db.refresh(ag)

    logs.registrar(
        db, acao="agendamento_criado", request=request,
        usuario_id=usuario.id, username=usuario.username,
        relatorio_id=ag.relatorio_id,
        parametros={"agendamento_id": ag.id, "nome": ag.nome, "freq": ag.frequencia},
        sucesso=True,
    )

    # Monta a resposta com token em claro.
    base = AgendamentoResumo.model_validate(ag).model_dump()
    return AgendamentoCriadoResponse(**base, token_claro=token_claro)


@router.patch("/{agendamento_id}", response_model=AgendamentoResumo)
def editar(
    agendamento_id: int,
    payload: AgendamentoCriar,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> AgendamentoResumo:
    """
    Substitui a configuração do agendamento. Token não muda (regenerar
    via endpoint próprio). proxima_execucao é recalculada.
    """
    ag = _buscar_proprio(db, usuario, agendamento_id)
    if not pode_acessar(db, usuario, payload.relatorio_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para esse relatório.",
        )
    ag.nome = payload.nome
    ag.descricao = payload.descricao
    ag.tipo = payload.tipo
    ag.relatorio_id = payload.relatorio_id
    ag.filtros_base = payload.filtros_base
    ag.sql_texto = payload.sql_texto
    ag.preset_datas = payload.preset_datas
    ag.frequencia = payload.frequencia
    ag.dias_semana = payload.dias_semana
    ag.dia_mes = payload.dia_mes
    ag.hora = payload.hora
    ag.minuto = payload.minuto
    ag.ativo = payload.ativo
    ag.estrategia_nome = payload.estrategia_nome
    ag.retencao_dias = payload.retencao_dias
    ag.proxima_execucao = calcular_proxima_execucao(ag) if ag.ativo else None
    db.commit()
    db.refresh(ag)
    logs.registrar(
        db, acao="agendamento_editado", request=request,
        usuario_id=usuario.id, username=usuario.username,
        relatorio_id=ag.relatorio_id,
        parametros={"agendamento_id": ag.id}, sucesso=True,
    )
    return AgendamentoResumo.model_validate(ag)


@router.delete("/{agendamento_id}", status_code=204)
def apagar(
    agendamento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> Response:
    """Apaga o agendamento. Cascade apaga as execuções."""
    ag = _buscar_proprio(db, usuario, agendamento_id)
    db.delete(ag)
    db.commit()
    logs.registrar(
        db, acao="agendamento_removido", request=request,
        usuario_id=usuario.id, username=usuario.username,
        relatorio_id=ag.relatorio_id,
        parametros={"agendamento_id": agendamento_id}, sucesso=True,
    )
    return Response(status_code=204)


@router.post("/{agendamento_id}/regenerar-token", response_model=AgendamentoCriadoResponse)
def regenerar_token(
    agendamento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> AgendamentoCriadoResponse:
    """
    Gera um token novo pra esse agendamento. O anterior é invalidado
    imediatamente — scripts antigos param de funcionar. Útil se o usuário
    perder o script ou suspeitar de vazamento.
    """
    ag = _buscar_proprio(db, usuario, agendamento_id)
    token_claro, token_hash, token_prefixo = gerar_token(ag.id)
    ag.token_hash = token_hash
    ag.token_prefixo = token_prefixo
    db.commit()
    db.refresh(ag)
    logs.registrar(
        db, acao="agendamento_token_regenerado", request=request,
        usuario_id=usuario.id, username=usuario.username,
        relatorio_id=ag.relatorio_id,
        parametros={"agendamento_id": ag.id}, sucesso=True,
    )
    base = AgendamentoResumo.model_validate(ag).model_dump()
    return AgendamentoCriadoResponse(**base, token_claro=token_claro)


@router.post("/{agendamento_id}/testar", response_model=ExecucaoResumo)
def testar(
    agendamento_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> ExecucaoResumo:
    """Dispara agora, sem alterar o cronograma (ultima/proxima_execucao)."""
    ag = _buscar_proprio(db, usuario, agendamento_id)
    exec_ = disparar_agendamento(db, ag, teste=True)
    logs.registrar(
        db, acao="agendamento_testado", request=request,
        usuario_id=usuario.id, username=usuario.username,
        relatorio_id=ag.relatorio_id,
        parametros={"agendamento_id": ag.id, "execucao_id": exec_.id},
        sucesso=True,
    )
    return ExecucaoResumo.model_validate(exec_)


@router.get("/{agendamento_id}/execucoes", response_model=list[ExecucaoResumo])
def listar_execucoes(
    agendamento_id: int,
    limite: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> list[ExecucaoResumo]:
    """Histórico de execuções (mais recentes primeiro)."""
    ag = _buscar_proprio(db, usuario, agendamento_id)
    rows = (
        db.query(AgendamentoExecucao)
        .filter(AgendamentoExecucao.agendamento_id == ag.id)
        .order_by(desc(AgendamentoExecucao.criado_em))
        .limit(limite)
        .all()
    )
    return [ExecucaoResumo.model_validate(r) for r in rows]


@router.get("/{agendamento_id}/execucoes/{execucao_id}/download")
def baixar_execucao_ui(
    agendamento_id: int,
    execucao_id: int,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> FileResponse:
    """
    Download via UI (cookie de sessão). Reusa o CSV salvo pelo JobExtracao
    vinculado à execução.
    """
    _buscar_proprio(db, usuario, agendamento_id)
    exec_ = db.get(AgendamentoExecucao, execucao_id)
    if exec_ is None or exec_.agendamento_id != agendamento_id:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return _responder_arquivo(db, exec_, request, usuario)


@router.post("/{agendamento_id}/script", response_model=ScriptGerado)
def gerar_script_endpoint(
    agendamento_id: int,
    so: str = Query("windows", pattern=r"^(windows|linux|mac)$"),
    x_token_claro: str = Header(..., alias="X-Token-Claro"),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> ScriptGerado:
    """
    Devolve o script sincronizador PRONTO pra baixar.

    POST (não GET) porque o token em claro é embutido no script — não quero
    esse valor em logs de GET. O frontend recebe o token no response de criação
    ou regeneração e passa aqui no header X-Token-Claro. Jamais salvamos o
    claro no backend depois disso.

    Confere que o `x_token_claro` enviado bate com o hash do agendamento
    (defense-in-depth: alguém com cookie da sessão mas token errado não gera script).
    """
    ag = _buscar_proprio(db, usuario, agendamento_id)
    if not token_bate(x_token_claro, ag):
        raise HTTPException(
            status_code=400,
            detail=(
                "Token enviado não corresponde ao agendamento. "
                "Regenere o token em 'Regerar token' e tente de novo."
            ),
        )
    api_base = _montar_api_base()
    nome_arq, conteudo, instr, ext = gerar_para_so(
        so,
        agendamento_id=ag.id,
        nome_agendamento=ag.nome,
        token_claro=x_token_claro,
        api_base=api_base,
    )
    return ScriptGerado(
        nome_arquivo=nome_arq, conteudo=conteudo, instrucoes=instr, extensao=ext
    )


def _montar_api_base() -> str:
    """
    Endereço base da API que será embutido no script.

    Preferência: variável `API_BASE_EXTERNA` (configurável no .env — usado em
    produção). Fallback: hostname + 8000.
    """
    return os.getenv("API_BASE_EXTERNA") or "http://localhost:8000"


# =============================================================================
# Endpoints consumidos pelo SCRIPT (auth via token)
# =============================================================================

async def _agendamento_pelo_token(
    agendamento_id: int,
    x_agendamento_token: str = Header(..., alias="X-Agendamento-Token"),
    db: Session = Depends(get_db),
) -> Agendamento:
    """Dependency: busca o agendamento e confere o token. 401 em qualquer falha."""
    id_do_token = extrair_id_do_token(x_agendamento_token)
    if id_do_token is None or id_do_token != agendamento_id:
        raise HTTPException(status_code=401, detail="Token inválido.")
    ag = db.get(Agendamento, agendamento_id)
    if ag is None or not token_bate(x_agendamento_token, ag):
        raise HTTPException(status_code=401, detail="Token inválido.")
    if not ag.ativo:
        raise HTTPException(status_code=403, detail="Agendamento desativado.")
    return ag


@router.get(
    "/{agendamento_id}/execucoes/pendentes",
    response_model=list[ExecucaoPendenteParaScript],
)
def pendentes_pro_script(
    agendamento_id: int,
    maquina_id: str = Query(..., min_length=1, max_length=100),
    ag: Agendamento = Depends(_agendamento_pelo_token),
    db: Session = Depends(get_db),
) -> list[ExecucaoPendenteParaScript]:
    """
    Execuções CONCLUÍDAS que essa máquina ainda não baixou.
    O script chama isso hora em hora.
    """
    rows = (
        db.query(AgendamentoExecucao)
        .filter(
            AgendamentoExecucao.agendamento_id == ag.id,
            AgendamentoExecucao.status == EXEC_CONCLUIDA,
        )
        .order_by(desc(AgendamentoExecucao.criado_em))
        .limit(50)  # limite defensivo — script processa aos poucos
        .all()
    )
    resultado: list[ExecucaoPendenteParaScript] = []
    for r in rows:
        baixou_essa = (r.baixada_por or [])
        if maquina_id in baixou_essa:
            continue
        resultado.append(
            ExecucaoPendenteParaScript(
                id=r.id,
                nome_arquivo=r.nome_arquivo,
                tamanho_bytes=r.tamanho_bytes,
                total_linhas=r.total_linhas,
                concluido_em=r.concluido_em,
                download_url=f"/agendamentos/{ag.id}/execucoes/{r.id}/download-script",
            )
        )
    return resultado


@router.get("/{agendamento_id}/execucoes/{execucao_id}/download-script")
def download_pro_script(
    agendamento_id: int,
    execucao_id: int,
    request: Request,
    ag: Agendamento = Depends(_agendamento_pelo_token),
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download via script (header X-Agendamento-Token)."""
    exec_ = db.get(AgendamentoExecucao, execucao_id)
    if exec_ is None or exec_.agendamento_id != ag.id:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    return _responder_arquivo(db, exec_, request, usuario=None, via_script=True)


@router.post("/{agendamento_id}/execucoes/{execucao_id}/baixada", status_code=204)
def callback_baixada(
    agendamento_id: int,
    execucao_id: int,
    payload: CallbackDownload,
    request: Request,
    ag: Agendamento = Depends(_agendamento_pelo_token),
    db: Session = Depends(get_db),
) -> Response:
    """
    Script avisa o server: "baixei (ou tentei) essa execução". Backend marca
    a máquina na lista `baixada_por` (ok=True) ou só registra o erro no log
    (ok=False), sem marcar — assim o script volta na próxima rodada.
    """
    exec_ = db.get(AgendamentoExecucao, execucao_id)
    if exec_ is None or exec_.agendamento_id != ag.id:
        raise HTTPException(status_code=404, detail="Execução não encontrada.")
    if payload.ok:
        lista = list(exec_.baixada_por or [])
        if payload.maquina_id not in lista:
            lista.append(payload.maquina_id)
        exec_.baixada_por = lista
        db.commit()
        logs.registrar(
            db, acao="agendamento_execucao_baixada", request=request,
            usuario_id=ag.usuario_id, username=ag.username,
            relatorio_id=ag.relatorio_id,
            parametros={
                "agendamento_id": ag.id, "execucao_id": execucao_id,
                "maquina_id": payload.maquina_id,
            },
            sucesso=True,
        )
    else:
        logs.registrar(
            db, acao="agendamento_execucao_baixada", request=request,
            usuario_id=ag.usuario_id, username=ag.username,
            relatorio_id=ag.relatorio_id,
            parametros={
                "agendamento_id": ag.id, "execucao_id": execucao_id,
                "maquina_id": payload.maquina_id, "erro": payload.erro,
            },
            sucesso=False, erro_mensagem=payload.erro or "download falhou",
        )
    return Response(status_code=204)


# =============================================================================
# Helper comum de resposta de arquivo
# =============================================================================

def _responder_arquivo(
    db: Session,
    exec_: AgendamentoExecucao,
    request: Request,
    usuario: Optional[Usuario],
    via_script: bool = False,
) -> FileResponse:
    """FileResponse pra UI ou script, com os mesmos checks."""
    from app.models.job import STATUS_CONCLUIDO, JobExtracao
    if exec_.status != EXEC_CONCLUIDA:
        raise HTTPException(
            status_code=409,
            detail=f"Execução não está concluída (status={exec_.status}).",
        )
    job = db.get(JobExtracao, exec_.job_id) if exec_.job_id else None
    if job is None or job.status != STATUS_CONCLUIDO:
        raise HTTPException(status_code=410, detail="Arquivo expirado ou indisponível.")
    if not job.caminho_csv or not os.path.exists(job.caminho_csv):
        raise HTTPException(status_code=410, detail="Arquivo expirado (CSV não encontrado em disco).")

    logs.registrar(
        db,
        acao="agendamento_execucao_download" + ("_script" if via_script else "_ui"),
        request=request,
        usuario_id=usuario.id if usuario else None,
        username=usuario.username if usuario else None,
        relatorio_id=exec_.params_resolvidos.get("relatorio_id") if exec_.params_resolvidos else None,
        parametros={"agendamento_id": exec_.agendamento_id, "execucao_id": exec_.id},
        sucesso=True,
    )

    return FileResponse(
        path=job.caminho_csv,
        media_type="text/csv; charset=utf-8",
        filename=exec_.nome_arquivo or f"execucao_{exec_.id}.csv",
        headers={"Access-Control-Expose-Headers": "Content-Disposition"},
    )
