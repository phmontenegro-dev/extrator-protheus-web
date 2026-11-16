"""
Endpoints administrativos — todos exigem is_admin=True.

  GET    /admin/usuarios                               lista
  POST   /admin/usuarios                               cria
  PATCH  /admin/usuarios/{id}                          edita (nome/email/admin/ativo)
  POST   /admin/usuarios/{id}/resetar-senha            redefine senha
  GET    /admin/usuarios/{id}/permissoes               lista permissões do usuário
  PUT    /admin/usuarios/{id}/permissoes               substitui a lista
  GET    /admin/logs                                   logs paginados com filtros

Guardrails:
  - Admin NÃO pode se auto-desativar nem tirar o próprio is_admin
    (evita se trancar pra fora acidentalmente).
  - Último admin ativo não pode ser desativado / despromovido.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_admin_atual
from app.auth.password import SenhaInvalidaError, gerar_hash
from app.database import get_db
from app.models.log_acesso import LogAcesso
from app.models.permissao import PermissaoRelatorio
from app.models.sessao import Sessao
from app.models.usuario import Usuario
from app.relatorios_prontos.registry import existe as relatorio_existe
from app.schemas.admin import (
    LogItem,
    LogsPagina,
    PermissoesPayload,
    PermissoesResponse,
    ResetSenhaPayload,
    UsuarioCreate,
    UsuarioDetalhe,
    UsuarioUpdate,
)
from app.utils import logs as logs_util


router = APIRouter(prefix="/admin", tags=["admin"])


# =============================================================================
# Helpers internos
# =============================================================================

def _buscar_usuario(db: Session, usuario_id: int) -> Usuario:
    """Retorna o usuário ou 404."""
    u = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if u is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado.")
    return u


def _total_admins_ativos(db: Session, excluindo_id: Optional[int] = None) -> int:
    """Conta admins ativos, opcionalmente excluindo um ID (para checks 'se eu mexer agora, sobra quem?')."""
    q = db.query(func.count(Usuario.id)).filter(
        Usuario.is_admin.is_(True),
        Usuario.ativo.is_(True),
    )
    if excluindo_id is not None:
        q = q.filter(Usuario.id != excluindo_id)
    return int(q.scalar() or 0)


def _validar_permissoes(relatorios: list[str]) -> list[str]:
    """Normaliza (deduplicação + trim) e rejeita ids desconhecidos."""
    normalizados = sorted({r.strip() for r in relatorios if r.strip()})
    desconhecidos = [r for r in normalizados if not relatorio_existe(r)]
    if desconhecidos:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Relatórios desconhecidos: {', '.join(desconhecidos)}",
        )
    return normalizados


def _aplicar_permissoes(
    db: Session,
    usuario_id: int,
    relatorios: list[str],
    concedido_por_id: int,
) -> list[str]:
    """
    Substitui a lista de permissões do usuário pela nova lista.
    Retorna a lista final (normalizada).
    """
    normalizados = _validar_permissoes(relatorios)
    db.query(PermissaoRelatorio).filter(
        PermissaoRelatorio.usuario_id == usuario_id
    ).delete()
    for rid in normalizados:
        db.add(PermissaoRelatorio(
            usuario_id=usuario_id,
            relatorio_id=rid,
            concedido_por_id=concedido_por_id,
        ))
    db.commit()
    return normalizados


def _gerar_hash_ou_422(senha: str) -> str:
    """Wrapper que converte SenhaInvalidaError em HTTP 422."""
    try:
        return gerar_hash(senha)
    except SenhaInvalidaError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


# =============================================================================
# Usuários — CRUD
# =============================================================================

@router.get("/usuarios", response_model=list[UsuarioDetalhe])
def listar_usuarios(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_admin_atual),
) -> list[UsuarioDetalhe]:
    rows = db.query(Usuario).order_by(Usuario.username).all()
    return [UsuarioDetalhe.model_validate(u) for u in rows]


@router.post("/usuarios", response_model=UsuarioDetalhe, status_code=status.HTTP_201_CREATED)
def criar_usuario(
    payload: UsuarioCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
) -> UsuarioDetalhe:
    username = payload.username.strip().lower()
    if not username:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Username vazio.")

    existente = db.query(Usuario).filter(Usuario.username == username).first()
    if existente is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Usuário '{username}' já existe.")

    novo = Usuario(
        username=username,
        nome_completo=payload.nome_completo.strip(),
        email=(payload.email or "").strip() or None,
        senha_hash=_gerar_hash_ou_422(payload.senha),
        is_admin=payload.is_admin,
        ativo=True,
    )
    db.add(novo)
    db.commit()
    db.refresh(novo)

    # Permissões iniciais só pra não-admin (admin já vê tudo).
    if not novo.is_admin and payload.permissoes:
        _aplicar_permissoes(db, novo.id, payload.permissoes, admin.id)

    logs_util.registrar(
        db, acao="admin_criou_usuario", request=request,
        usuario_id=admin.id, username=admin.username,
        parametros={"alvo_id": novo.id, "alvo_username": novo.username,
                    "is_admin": novo.is_admin, "permissoes": payload.permissoes},
    )
    return UsuarioDetalhe.model_validate(novo)


@router.patch("/usuarios/{usuario_id}", response_model=UsuarioDetalhe)
def editar_usuario(
    usuario_id: int,
    payload: UsuarioUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
) -> UsuarioDetalhe:
    alvo = _buscar_usuario(db, usuario_id)
    mudancas: dict = {}

    if payload.nome_completo is not None:
        nome = payload.nome_completo.strip()
        if nome and nome != alvo.nome_completo:
            mudancas["nome_completo"] = (alvo.nome_completo, nome)
            alvo.nome_completo = nome

    if payload.email is not None:
        novo_email = payload.email.strip() or None
        if novo_email != alvo.email:
            mudancas["email"] = (alvo.email, novo_email)
            alvo.email = novo_email

    if payload.is_admin is not None and payload.is_admin != alvo.is_admin:
        # Auto-rebaixamento é bloqueado (evita se trancar sem acesso ao admin).
        if alvo.id == admin.id and payload.is_admin is False:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Você não pode remover a própria permissão de admin.",
            )
        # Último admin ativo não pode perder admin.
        if alvo.is_admin and alvo.ativo and payload.is_admin is False:
            if _total_admins_ativos(db, excluindo_id=alvo.id) == 0:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Operação deixaria o sistema sem nenhum admin ativo.",
                )
        mudancas["is_admin"] = (alvo.is_admin, payload.is_admin)
        alvo.is_admin = payload.is_admin

    if payload.ativo is not None and payload.ativo != alvo.ativo:
        # Auto-desativação bloqueada.
        if alvo.id == admin.id and payload.ativo is False:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Você não pode desativar o próprio usuário.",
            )
        # Último admin ativo não pode ser desativado.
        if alvo.is_admin and alvo.ativo and payload.ativo is False:
            if _total_admins_ativos(db, excluindo_id=alvo.id) == 0:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Operação deixaria o sistema sem nenhum admin ativo.",
                )
        mudancas["ativo"] = (alvo.ativo, payload.ativo)
        alvo.ativo = payload.ativo

        # Ao desativar, invalida sessões ativas desse usuário.
        if payload.ativo is False:
            db.query(Sessao).filter(Sessao.usuario_id == alvo.id).delete()

    if not mudancas:
        return UsuarioDetalhe.model_validate(alvo)

    db.commit()
    db.refresh(alvo)

    logs_util.registrar(
        db, acao="admin_editou_usuario", request=request,
        usuario_id=admin.id, username=admin.username,
        parametros={"alvo_id": alvo.id, "alvo_username": alvo.username,
                    "mudancas": {k: {"de": str(a), "para": str(b)} for k, (a, b) in mudancas.items()}},
    )
    return UsuarioDetalhe.model_validate(alvo)


@router.post("/usuarios/{usuario_id}/resetar-senha", status_code=status.HTTP_204_NO_CONTENT)
def resetar_senha(
    usuario_id: int,
    payload: ResetSenhaPayload,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
):
    alvo = _buscar_usuario(db, usuario_id)
    alvo.senha_hash = _gerar_hash_ou_422(payload.nova_senha)
    # Invalida sessões ativas desse usuário — força logar com a senha nova.
    db.query(Sessao).filter(Sessao.usuario_id == alvo.id).delete()
    db.commit()

    logs_util.registrar(
        db, acao="admin_resetou_senha", request=request,
        usuario_id=admin.id, username=admin.username,
        parametros={"alvo_id": alvo.id, "alvo_username": alvo.username},
    )


# =============================================================================
# Permissões
# =============================================================================

@router.get("/usuarios/{usuario_id}/permissoes", response_model=PermissoesResponse)
def obter_permissoes(
    usuario_id: int,
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_admin_atual),
) -> PermissoesResponse:
    alvo = _buscar_usuario(db, usuario_id)
    rows = (
        db.query(PermissaoRelatorio.relatorio_id)
        .filter(PermissaoRelatorio.usuario_id == alvo.id)
        .order_by(PermissaoRelatorio.relatorio_id)
        .all()
    )
    return PermissoesResponse(usuario_id=alvo.id, relatorios=[r[0] for r in rows])


@router.put("/usuarios/{usuario_id}/permissoes", response_model=PermissoesResponse)
def atualizar_permissoes(
    usuario_id: int,
    payload: PermissoesPayload,
    request: Request,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(get_admin_atual),
) -> PermissoesResponse:
    alvo = _buscar_usuario(db, usuario_id)
    normalizados = _aplicar_permissoes(db, alvo.id, payload.relatorios, admin.id)

    logs_util.registrar(
        db, acao="admin_atualizou_permissoes", request=request,
        usuario_id=admin.id, username=admin.username,
        parametros={"alvo_id": alvo.id, "alvo_username": alvo.username,
                    "relatorios": normalizados},
    )
    return PermissoesResponse(usuario_id=alvo.id, relatorios=normalizados)


# =============================================================================
# Logs
# =============================================================================

@router.get("/logs", response_model=LogsPagina)
def listar_logs(
    db: Session = Depends(get_db),
    _admin: Usuario = Depends(get_admin_atual),
    username: Optional[str] = Query(default=None, description="Filtra por username exato"),
    acao: Optional[str] = Query(default=None, description="Filtra por ação"),
    relatorio_id: Optional[str] = Query(default=None),
    desde_dias: Optional[int] = Query(default=7, ge=0, le=365,
                                      description="Últimos N dias (0 = sem limite)"),
    somente_falhas: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> LogsPagina:
    q = db.query(LogAcesso)

    if username:
        q = q.filter(LogAcesso.username == username)
    if acao:
        q = q.filter(LogAcesso.acao == acao)
    if relatorio_id:
        q = q.filter(LogAcesso.relatorio_id == relatorio_id)
    if somente_falhas:
        q = q.filter(LogAcesso.sucesso.is_(False))
    if desde_dias and desde_dias > 0:
        desde = datetime.now(timezone.utc) - timedelta(days=desde_dias)
        q = q.filter(LogAcesso.timestamp >= desde)

    total = int(q.with_entities(func.count(LogAcesso.id)).scalar() or 0)
    rows = (
        q.order_by(LogAcesso.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return LogsPagina(
        itens=[LogItem.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
