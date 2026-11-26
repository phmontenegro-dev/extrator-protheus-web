"""
Registro do relatório pronto carteira_pedidos no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.carteira_pedidos.extrair import extrair_carteira_pedidos


def _extrair(**_):
    return extrair_carteira_pedidos()


relatorio = RelatorioPronto(
    id="carteira_pedidos",
    nome="Carteira de Pedidos",
    descricao=(
        "Carteira denormalizada de pedidos de venda (SC6/SC5 + SA1/SA2 + SA3 + SC2 + SC9): "
        "janela de emissão dos últimos 13 meses OU itens ainda com saldo a atender. Logística."
    ),
    filtros="nenhum",
    extrair=_extrair,
)
