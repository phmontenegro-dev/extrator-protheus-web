"""
Registro do relatório pronto sb8_suzano no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sb8_suzano.extrair import extrair_sb8_suzano
from app.relatorios_prontos.sb8_suzano.tratar import tratar_dataframe


def _extrair(**_):
    return extrair_sb8_suzano()


relatorio = RelatorioPronto(
    id='sb8_suzano',
    nome='SB8 SUZANO — Saldos por Lote',
    descricao='Saldos de estoque com lote Suzano (filtros fixos: saldo > 1 + lote %SZ%).',
    filtros='nenhum',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
