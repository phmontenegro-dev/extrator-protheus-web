"""
Registro do relatório pronto sd4_suzano no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sd4_suzano.extrair import extrair_sd4_suzano
from app.relatorios_prontos.sd4_suzano.tratar import tratar_dataframe


def _extrair(data_inicio: str, data_fim: str, **_):
    return extrair_sd4_suzano(data_inicio, data_fim)


relatorio = RelatorioPronto(
    id='sd4_suzano',
    nome='SD4 SUZANO — Empenhos',
    descricao='Empenhos de insumo com lote Suzano, filtrados pela data de empenho.',
    filtros='periodo',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
