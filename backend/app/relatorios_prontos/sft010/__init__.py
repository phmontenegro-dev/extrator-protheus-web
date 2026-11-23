"""
Registro do relatório pronto sft010 no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sft010.extrair import extrair_sft010
from app.relatorios_prontos.sft010.tratar import tratar_dataframe


def _extrair(data_inicio: str, data_fim: str, **_):
    return extrair_sft010(data_inicio, data_fim)


relatorio = RelatorioPronto(
    id='sft010',
    nome='SFT010 — Documentos de Entrada e Saída',
    descricao='Documentos fiscais (SFT) com cliente/fornecedor, grupo, custos e duas fotos de estoque (SB9) nos meses de contorno do período.',
    filtros='periodo',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
