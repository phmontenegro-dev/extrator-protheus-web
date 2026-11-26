"""
Registro do relatório pronto sb1_produtos no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sb1_produtos.extrair import extrair_sb1_produtos


def _extrair(**_):
    return extrair_sb1_produtos()


relatorio = RelatorioPronto(
    id="sb1_produtos",
    nome="SB1 — Cadastro de Produtos",
    descricao="Cadastro completo de produtos (SB1010), todos os registros não deletados. Logística.",
    filtros="nenhum",
    extrair=_extrair,
)
