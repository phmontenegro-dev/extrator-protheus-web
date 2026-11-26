"""
Registro do relatório pronto sd5_requisicoes_lotes no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sd5_requisicoes_lotes.extrair import extrair_sd5_requisicoes_lotes


def _extrair(**_):
    return extrair_sd5_requisicoes_lotes()


relatorio = RelatorioPronto(
    id="sd5_requisicoes_lotes",
    nome="SD5 — Requisições de Lotes",
    descricao="Requisições de lotes com OP associada (SD5010), não deletados. Logística.",
    filtros="nenhum",
    extrair=_extrair,
)
