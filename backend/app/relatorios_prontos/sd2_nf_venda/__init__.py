"""
Registro do relatório pronto sd2_nf_venda no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sd2_nf_venda.extrair import extrair_sd2_nf_venda


def _extrair(**_):
    return extrair_sd2_nf_venda()


relatorio = RelatorioPronto(
    id="sd2_nf_venda",
    nome="SD2 — Notas Fiscais de Venda",
    descricao="Notas fiscais de venda (SD2010) dos últimos 13 meses em diante. Colunas em PT-BR com valores já formatados. Logística.",
    filtros="nenhum",
    extrair=_extrair,
)
