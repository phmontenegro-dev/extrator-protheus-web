"""
Registro do relatório pronto sb6_saldo_terceiros no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sb6_saldo_terceiros.extrair import extrair_sb6_saldo_terceiros


def _extrair(**_):
    return extrair_sb6_saldo_terceiros()


relatorio = RelatorioPronto(
    id="sb6_saldo_terceiros",
    nome="SB6 — Saldo de Terceiros por Produto",
    descricao="Saldos de produtos em poder de terceiros (SB6010), todos os registros não deletados. Logística.",
    filtros="nenhum",
    extrair=_extrair,
)
