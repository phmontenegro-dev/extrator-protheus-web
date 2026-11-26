"""
Registro do relatório pronto sb2_saldo_fisico no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sb2_saldo_fisico.extrair import extrair_sb2_saldo_fisico


def _extrair(**_):
    return extrair_sb2_saldo_fisico()


relatorio = RelatorioPronto(
    id="sb2_saldo_fisico",
    nome="SB2 — Saldo Físico por Produto",
    descricao="Saldo físico por produto e armazém (SB2010), todos os registros não deletados. Logística.",
    filtros="nenhum",
    extrair=_extrair,
)
