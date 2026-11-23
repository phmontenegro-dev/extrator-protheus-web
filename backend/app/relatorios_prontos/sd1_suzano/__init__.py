"""
Registro do relatório pronto sd1_suzano no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sd1_suzano.extrair import extrair_sd1_suzano
from app.relatorios_prontos.sd1_suzano.tratar import tratar_dataframe


def _extrair(**_):
    return extrair_sd1_suzano()


relatorio = RelatorioPronto(
    id='sd1_suzano',
    nome='SD1 SUZANO — Documentos de Entrada',
    descricao='Documentos de entrada com lote Suzano (sem parâmetros).',
    filtros='nenhum',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
