"""
Registro do relatório pronto qpr010 no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.qpr010.extrair import extrair_qpr010
from app.relatorios_prontos.qpr010.tratar import tratar_dataframe


def _extrair(filial: str, data_inicio: str, data_fim: str, **_):
    return extrair_qpr010(filial, data_inicio, data_fim)


relatorio = RelatorioPronto(
    id='qpr010',
    nome='QPR010 — Medições de Qualidade',
    descricao='Medições de qualidade (QPR) com joins em QPS/QPQ/QPL/SH6/SB1/QP1/QP7/QAA, consolidando data+hora, lote final, bobina filha e dedup por lote+ensaio.',
    filtros='filial_periodo',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
