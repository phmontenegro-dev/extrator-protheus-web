"""
Rate limit de login por IP.

Reaproveita a tabela logs_acesso (não precisa criar outra): conta quantos
logins falhados aquele IP teve nos últimos N minutos. Se bater o limite,
bloqueia.

Simples, sem Redis, sem dependência extra. Login não é caminho crítico de
performance, então uma query a mais por tentativa é aceitável.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.log_acesso import LogAcesso


MAX_TENTATIVAS = 5
JANELA_MINUTOS = 15


def tentativas_recentes(db: Session, ip: str) -> int:
    """Quantas tentativas falhas o IP teve na janela recente."""
    if not ip:
        return 0
    desde = datetime.now(timezone.utc) - timedelta(minutes=JANELA_MINUTOS)
    q = (
        db.query(func.count(LogAcesso.id))
        .filter(LogAcesso.acao == "login_falhou")
        .filter(LogAcesso.ip_origem == ip)
        .filter(LogAcesso.timestamp >= desde)
    )
    return int(q.scalar() or 0)


def ip_bloqueado(db: Session, ip: str) -> bool:
    return tentativas_recentes(db, ip) >= MAX_TENTATIVAS


def minutos_ate_desbloqueio(db: Session, ip: str) -> int:
    """
    Minutos restantes até o IP poder tentar de novo. Arredonda para cima.
    Retorna 0 se não está bloqueado.
    """
    if not ip:
        return 0
    desde = datetime.now(timezone.utc) - timedelta(minutes=JANELA_MINUTOS)
    # Pega o timestamp da PRIMEIRA tentativa dentro da janela — é a que
    # vai sair da janela primeiro.
    primeira = (
        db.query(func.min(LogAcesso.timestamp))
        .filter(LogAcesso.acao == "login_falhou")
        .filter(LogAcesso.ip_origem == ip)
        .filter(LogAcesso.timestamp >= desde)
        .scalar()
    )
    if primeira is None:
        return 0
    expira_em = primeira + timedelta(minutes=JANELA_MINUTOS)
    agora = datetime.now(timezone.utc)
    if expira_em <= agora:
        return 0
    return max(1, int((expira_em - agora).total_seconds() // 60) + 1)
