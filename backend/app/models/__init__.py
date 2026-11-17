"""
Expõe todos os models em um único ponto.

Importante para o Alembic: ele precisa que os models estejam carregados na
mesma Base para detectar as tabelas via autogenerate. Ao importar daqui em
alembic/env.py, todos os models são registrados.
"""
from app.models.usuario import Usuario
from app.models.permissao import PermissaoRelatorio
from app.models.log_acesso import LogAcesso
from app.models.sessao import Sessao
from app.models.area import Area
from app.models.relatorio_area import RelatorioArea

__all__ = [
    "Usuario",
    "PermissaoRelatorio",
    "LogAcesso",
    "Sessao",
    "Area",
    "RelatorioArea",
]
