"""
Registro do relatório pronto sd3010 no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sd3010.extrair import extrair_sd3010
from app.relatorios_prontos.sd3010.tratar import tratar_dataframe


def _extrair(data_inicio: str, data_fim: str, **_):
    return extrair_sd3010(data_inicio, data_fim)


relatorio = RelatorioPronto(
    id='sd3010',
    nome='SD3010 — Movimentações Internas',
    descricao='Movimentações internas de estoque vinculadas a OP, com produto e grupo.',
    filtros='periodo',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
