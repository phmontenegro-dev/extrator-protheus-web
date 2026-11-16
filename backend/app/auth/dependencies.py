"""
FastAPI dependencies para autenticação / autorização.

Uso típico em qualquer rota protegida:

    @router.get("/alguma-coisa")
    def rota(usuario: Usuario = Depends(get_usuario_atual)):
        ...

    @router.get("/admin/...")
    def rota_admin(usuario: Usuario = Depends(get_admin_atual)):
        ...
"""
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.auth.session import COOKIE_NAME, validar_e_renovar
from app.database import get_db
from app.models.usuario import Usuario


def get_usuario_atual(
    request: Request,
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Extrai o usuário da sessão (cookie httpOnly).

    Retorna 401 em qualquer problema: sem cookie, sessão inválida/expirada,
    ou usuário desativado/removido. Mensagem genérica — sem revelar qual
    dos casos aconteceu.
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado.",
        )

    sessao = validar_e_renovar(db, token)
    if sessao is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada.",
        )

    usuario = db.query(Usuario).filter(
        Usuario.id == sessao.usuario_id,
        Usuario.ativo.is_(True),
    ).first()
    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo ou removido.",
        )

    return usuario


def get_admin_atual(usuario: Usuario = Depends(get_usuario_atual)) -> Usuario:
    """
    Exige que o usuário autenticado seja admin. 403 caso contrário.
    """
    if not usuario.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permissão de administrador necessária.",
        )
    return usuario
