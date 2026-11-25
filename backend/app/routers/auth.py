"""
Endpoints de autenticação: login, logout, me.

Regras importantes:
  - Mensagem de erro de login é GENÉRICA (não revela se o username existe).
  - Rate limit por IP: 5 falhas em 15 min bloqueia.
  - Toda ação relevante gera log em logs_acesso.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth import rate_limit
from app.auth.dependencies import get_usuario_atual
from app.auth.password import SenhaInvalidaError, gerar_hash, verificar
from app.auth.session import COOKIE_NAME, criar_sessao, invalidar_sessao
from app.database import get_db
from app.models.sessao import Sessao
from app.models.usuario import Usuario
from app.schemas.auth import (
    AtualizarPerfilPayload,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    TrocarSenhaPayload,
    TrocarSenhaResponse,
    UsuarioOut,
)
from app.utils import logs


router = APIRouter(prefix="/auth", tags=["auth"])


MENSAGEM_GENERICA = "Usuário ou senha inválidos."


def _ip_do_request(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return ""


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """
    Autentica o usuário e cria uma sessão (cookie httpOnly).

    Códigos de erro:
      401 — usuário/senha inválido (genérico)
      429 — IP bloqueado por excesso de tentativas
    """
    ip = _ip_do_request(request)

    # 1) Rate limit — check antes de qualquer query custosa.
    if rate_limit.ip_bloqueado(db, ip):
        restante = rate_limit.minutos_ate_desbloqueio(db, ip)
        logs.registrar(
            db, acao="acesso_negado", request=request,
            username=payload.username, sucesso=False,
            erro_mensagem=f"IP bloqueado por rate limit (restam ~{restante}min)",
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Muitas tentativas de login desse IP. "
                f"Tente novamente em cerca de {restante} minuto(s)."
            ),
        )

    # 2) Busca o usuário. Usa a MESMA mensagem para "não existe" e "inativo".
    usuario = db.query(Usuario).filter(Usuario.username == payload.username).first()

    def _falhou(motivo_interno: str):
        """Loga a falha (com motivo real, só interno) e retorna 401 genérico."""
        logs.registrar(
            db, acao="login_falhou", request=request,
            username=payload.username, sucesso=False,
            erro_mensagem=motivo_interno,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=MENSAGEM_GENERICA)

    if usuario is None:
        _falhou("usuário não existe")
    if not usuario.ativo:
        _falhou("usuário desativado")
    if not verificar(payload.senha, usuario.senha_hash):
        _falhou("senha incorreta")

    # 3) OK — cria sessão, atualiza ultimo_login, loga sucesso.
    criar_sessao(db, usuario, response, request)
    usuario.ultimo_login = datetime.now(timezone.utc)
    db.commit()

    logs.registrar(
        db, acao="login_ok", request=request,
        usuario_id=usuario.id, username=usuario.username,
    )

    return LoginResponse(ok=True, usuario=UsuarioOut.model_validate(usuario))


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> LogoutResponse:
    """Encerra a sessão. Idempotente — logout sem sessão também retorna 200."""
    token = request.cookies.get(COOKIE_NAME)

    # Se tem token, tenta descobrir o usuário pra logar bonito antes de invalidar.
    usuario_id = None
    username = None
    if token:
        from app.models.sessao import Sessao
        sessao = db.query(Sessao).filter(Sessao.token == token).first()
        if sessao is not None:
            usuario = db.query(Usuario).filter(Usuario.id == sessao.usuario_id).first()
            if usuario is not None:
                usuario_id = usuario.id
                username = usuario.username

    invalidar_sessao(db, token, response)
    logs.registrar(
        db, acao="logout", request=request,
        usuario_id=usuario_id, username=username,
    )
    return LogoutResponse(ok=True)


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(get_usuario_atual)) -> UsuarioOut:
    """Retorna o usuário autenticado. Usada pelo frontend ao carregar."""
    return UsuarioOut.model_validate(usuario)


# =============================================================================
# Perfil do próprio usuário (Etapa 17)
# =============================================================================

@router.patch("/me", response_model=UsuarioOut)
def atualizar_me(
    payload: AtualizarPerfilPayload,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> UsuarioOut:
    """
    Atualiza nome e email do próprio usuário autenticado.

    Exige a senha atual como confirmação — defense-in-depth contra sequestro
    de email em sessão deixada aberta. 401 se a senha atual não bater.

    NÃO permite trocar `username`, `is_admin` ou `ativo` — pra isso, é o admin
    que mexe em /admin/usuarios/:id.
    """
    if not verificar(payload.senha_atual, usuario.senha_hash):
        logs.registrar(
            db, acao="perfil_editar_falhou", request=request,
            usuario_id=usuario.id, username=usuario.username,
            sucesso=False, erro_mensagem="senha atual incorreta",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha atual incorreta.",
        )

    campos_mudados: dict[str, str] = {}
    novo_nome = payload.nome_completo.strip()
    if novo_nome and novo_nome != usuario.nome_completo:
        campos_mudados["nome_completo"] = novo_nome
        usuario.nome_completo = novo_nome
    novo_email = payload.email
    if novo_email != (usuario.email or None):
        campos_mudados["email"] = novo_email or ""
        usuario.email = novo_email

    if campos_mudados:
        db.commit()
        db.refresh(usuario)

    logs.registrar(
        db, acao="perfil_editado", request=request,
        usuario_id=usuario.id, username=usuario.username,
        parametros={"campos": list(campos_mudados.keys())},
        sucesso=True,
    )
    return UsuarioOut.model_validate(usuario)


@router.post("/me/trocar-senha", response_model=TrocarSenhaResponse)
def trocar_senha(
    payload: TrocarSenhaPayload,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> TrocarSenhaResponse:
    """
    Troca a senha do próprio usuário autenticado.

    Fluxo:
      1. Valida senha atual (401 se errada)
      2. Valida a nova contra a política (8+ chars, 1 especial) — 422
      3. Gera hash bcrypt, salva
      4. Revoga TODAS as outras sessões do usuário (mantém a atual) —
         isso desloga o usuário em qualquer outro navegador/dispositivo,
         importante em caso de senha vazada
    """
    if not verificar(payload.senha_atual, usuario.senha_hash):
        logs.registrar(
            db, acao="trocar_senha_falhou", request=request,
            usuario_id=usuario.id, username=usuario.username,
            sucesso=False, erro_mensagem="senha atual incorreta",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Senha atual incorreta.",
        )

    if payload.senha_nova == payload.senha_atual:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="A nova senha deve ser diferente da atual.",
        )

    try:
        novo_hash = gerar_hash(payload.senha_nova)
    except SenhaInvalidaError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    usuario.senha_hash = novo_hash

    # Revoga outras sessões: mantém a atual (identificada pelo cookie) e
    # apaga todas as demais do mesmo usuário.
    token_atual = request.cookies.get(COOKIE_NAME)
    revogadas = (
        db.query(Sessao)
        .filter(Sessao.usuario_id == usuario.id, Sessao.token != token_atual)
        .delete(synchronize_session=False)
    )

    db.commit()

    logs.registrar(
        db, acao="trocar_senha_ok", request=request,
        usuario_id=usuario.id, username=usuario.username,
        parametros={"sessoes_revogadas": revogadas},
        sucesso=True,
    )

    return TrocarSenhaResponse(ok=True, sessoes_revogadas=int(revogadas))
