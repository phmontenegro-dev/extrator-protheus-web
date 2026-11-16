"""
Gerência de sessões (tabela `sessoes` + cookie httpOnly).

Regras:
  - Duração: 8 horas.
  - Rolling: se a sessão expira em menos de 1h, é estendida por mais 8h.
    Isso evita ter que atualizar o banco a cada request do mesmo usuário
    (que seria custoso) e ao mesmo tempo mantém a experiência de "ficou
    usando, continua logado".
  - Token: 48 bytes aleatórios (secrets.token_urlsafe) armazenados tanto no
    cookie quanto na tabela. O token NÃO é derivado do usuário — é opaco.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, Response
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.sessao import Sessao
from app.models.usuario import Usuario


COOKIE_NAME = "session_token"
DURACAO_HORAS = 8
RENOVAR_SE_FALTAR_MENOS_DE = timedelta(hours=1)


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _extrair_request_meta(request: Optional[Request]) -> tuple[Optional[str], Optional[str]]:
    """Retorna (ip, user_agent) a partir do Request — ou (None, None)."""
    if request is None:
        return None, None
    xff = request.headers.get("x-forwarded-for")
    if xff:
        ip = xff.split(",")[0].strip()
    elif request.client is not None:
        ip = request.client.host
    else:
        ip = None
    ua = request.headers.get("user-agent")
    return ip, (ua[:500] if ua else None)


def criar_sessao(
    db: Session,
    usuario: Usuario,
    response: Response,
    request: Optional[Request] = None,
) -> Sessao:
    """
    Cria uma sessão no banco e seta o cookie httpOnly na resposta.
    """
    settings = get_settings()
    token = secrets.token_urlsafe(48)
    ip, ua = _extrair_request_meta(request)

    sessao = Sessao(
        token=token,
        usuario_id=usuario.id,
        expira_em=_agora() + timedelta(hours=DURACAO_HORAS),
        ip_origem=ip,
        user_agent=ua,
    )
    db.add(sessao)
    db.commit()

    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=DURACAO_HORAS * 3600,
        httponly=True,
        # secure=True exige HTTPS. Em desenvolvimento (ENV=development)
        # deixamos False para o cookie funcionar via http://localhost.
        secure=(settings.env == "production"),
        samesite="lax",
    )
    return sessao


def invalidar_sessao(
    db: Session,
    token: Optional[str],
    response: Response,
) -> None:
    """Remove a sessão do banco e limpa o cookie no navegador."""
    if token:
        db.query(Sessao).filter(Sessao.token == token).delete()
        db.commit()
    response.delete_cookie(key=COOKIE_NAME)


def validar_e_renovar(db: Session, token: str) -> Optional[Sessao]:
    """
    Valida a sessão pelo token. Se válida e faltar < 1h para expirar,
    estende por mais 8h (rolling).

    Retorna a sessão (atualizada) ou None se inválida/expirada.
    """
    sessao = db.query(Sessao).filter(Sessao.token == token).first()
    if sessao is None:
        return None

    agora = _agora()
    if sessao.expira_em <= agora:
        # Expirada — remove e retorna None.
        db.delete(sessao)
        db.commit()
        return None

    # Rolling: só atualiza se faltar pouco.
    if sessao.expira_em - agora < RENOVAR_SE_FALTAR_MENOS_DE:
        sessao.expira_em = agora + timedelta(hours=DURACAO_HORAS)
        db.commit()

    return sessao
