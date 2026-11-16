"""
Helper central para gravar linhas na tabela logs_acesso.

Chamado por qualquer parte do código que queira registrar uma ação
auditável (login, logout, extração de relatório, acesso negado, erro, etc).

A ideia é ter UM caminho só pra escrever log — assim nada escapa e o schema
fica fácil de evoluir (se um dia adicionarmos uma coluna nova, muda aqui e
pronto).
"""
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.log_acesso import LogAcesso


def registrar(
    db: Session,
    *,
    acao: str,
    request: Optional[Request] = None,
    usuario_id: Optional[int] = None,
    username: Optional[str] = None,
    relatorio_id: Optional[str] = None,
    parametros: Optional[dict] = None,
    registros_retornados: Optional[int] = None,
    duracao_ms: Optional[int] = None,
    sucesso: bool = True,
    erro_mensagem: Optional[str] = None,
) -> LogAcesso:
    """
    Grava uma linha em logs_acesso.

    IP e user-agent são extraídos automaticamente do Request (quando passado).
    Faz commit na própria sessão — o chamador não precisa se preocupar com isso.
    """
    ip_origem = None
    user_agent = None
    if request is not None:
        # X-Forwarded-For só é confiável atrás de proxy reverso (nginx) —
        # em dev, request.client.host já é o IP real.
        xff = request.headers.get("x-forwarded-for")
        if xff:
            ip_origem = xff.split(",")[0].strip()
        elif request.client is not None:
            ip_origem = request.client.host
        user_agent = request.headers.get("user-agent")

    log = LogAcesso(
        acao=acao,
        usuario_id=usuario_id,
        username=username,
        relatorio_id=relatorio_id,
        parametros=parametros,
        registros_retornados=registros_retornados,
        duracao_ms=duracao_ms,
        ip_origem=ip_origem,
        user_agent=user_agent[:500] if user_agent else None,
        sucesso=sucesso,
        erro_mensagem=erro_mensagem,
    )
    db.add(log)
    db.commit()
    return log
