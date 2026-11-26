"""
Registro do relatório pronto sb8_extrato_lotes no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sb8_extrato_lotes.extrair import extrair_sb8_extrato_lotes


def _extrair(**_):
    return extrair_sb8_extrato_lotes()


relatorio = RelatorioPronto(
    id="sb8_extrato_lotes",
    nome="SB8 — Extrato de Lotes",
    descricao="Extrato de lotes com saldo diferente de zero (SB8010), não deletados. Logística.",
    filtros="nenhum",
    extrair=_extrair,
)
