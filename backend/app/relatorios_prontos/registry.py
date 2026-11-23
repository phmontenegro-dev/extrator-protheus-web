"""
Registry público — view compatível em cima da auto-descoberta (Etapa 11.6).

Antes da 11.6, essa lista era manual. Agora é derivada do que o loader
encontra em `app.relatorios_prontos.*`. O formato de dict externo é
preservado pros chamadores existentes (routers, menu dinâmico, etc).

Pra adicionar um relatório novo, NÃO mexa aqui — crie o pacote/arquivo
em `relatorios_prontos/` exportando `relatorio = RelatorioPronto(...)`.
"""
from typing import Literal, TypedDict

from app.relatorios_prontos.base import (
    RelatorioPronto,
    descobrir_relatorios,
    listar_registro,
)


TipoFiltro = Literal["nenhum", "periodo", "filial_periodo", "livre", "sql"]


class RelatorioInfo(TypedDict):
    id: str
    nome: str
    descricao: str
    filtros: TipoFiltro


# ---------------------------------------------------------------------------
# Tipos especiais que NÃO cabem na auto-descoberta: têm rotas próprias
# (/relatorio-livre/*, /sql-livre/*) e não seguem o modelo "extrair + tratar".
# Adicionamos explicitamente pra aparecerem no menu e no sistema de permissões.
# ---------------------------------------------------------------------------
TIPOS_ESPECIAIS: list[RelatorioInfo] = [
    {
        "id": "relatorio_livre",
        "nome": "Relatório Livre",
        "descricao": (
            "Extração crua de qualquer tabela do Protheus — escolha a tabela, "
            "as colunas desejadas e opcionalmente um período de datas."
        ),
        "filtros": "livre",
    },
    {
        "id": "codigo_sql",
        "nome": "Código SQL",
        "descricao": (
            "Execute consultas SELECT livres no Oracle Protheus. "
            "Ferramenta avançada para administradores — bloqueia qualquer "
            "comando que não seja de leitura."
        ),
        "filtros": "sql",
    },
]


def _montar_lista() -> list[RelatorioInfo]:
    """Monta a lista completa (prontos descobertos + livre/sql fixos)."""
    prontos = [
        RelatorioInfo(id=r.id, nome=r.nome, descricao=r.descricao, filtros=r.filtros)
        for r in listar_registro()
    ]
    # Ordena: prontos por nome, depois os especiais sempre no fim.
    prontos.sort(key=lambda r: r["nome"])
    return prontos + TIPOS_ESPECIAIS


# `RELATORIOS` vira uma propriedade "lazy" — a primeira importação dispara a
# descoberta. Expomos como variável pra manter compat com código que faz
# `from registry import RELATORIOS`.
RELATORIOS: list[RelatorioInfo] = _montar_lista()


def existe(relatorio_id: str) -> bool:
    return any(r["id"] == relatorio_id for r in RELATORIOS)


def buscar(relatorio_id: str) -> RelatorioInfo | None:
    for r in RELATORIOS:
        if r["id"] == relatorio_id:
            return r
    return None


def buscar_pronto(relatorio_id: str) -> RelatorioPronto | None:
    """Específico pra relatórios com extrair/tratar (não pros tipos especiais)."""
    return descobrir_relatorios().get(relatorio_id)
