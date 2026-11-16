"""
Helpers de autorização por relatório.

Regras:
  - Admin vê e extrai qualquer relatório, sem precisar de permissão explícita.
  - Usuário comum precisa de uma linha em permissoes_relatorio para cada
    relatório que vai acessar.
"""
from sqlalchemy.orm import Session

from app.models.permissao import PermissaoRelatorio
from app.models.usuario import Usuario


def relatorios_permitidos(db: Session, usuario: Usuario) -> set[str]:
    """
    Conjunto de relatorio_ids que o usuário pode acessar.

    Para admin, retorna um sentinela interpretado pelo chamador como "todos" —
    usando um set vazio aqui seria ambíguo com "nenhum", então quem precisar
    deve testar primeiro `usuario.is_admin` e pular esta chamada.
    """
    rows = (
        db.query(PermissaoRelatorio.relatorio_id)
        .filter(PermissaoRelatorio.usuario_id == usuario.id)
        .all()
    )
    return {r[0] for r in rows}


def pode_acessar(db: Session, usuario: Usuario, relatorio_id: str) -> bool:
    if usuario.is_admin:
        return True
    return relatorio_id in relatorios_permitidos(db, usuario)
