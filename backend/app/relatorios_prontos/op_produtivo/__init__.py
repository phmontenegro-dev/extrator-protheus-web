"""
Registro do relatório pronto op_produtivo no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.op_produtivo.extrair import extrair_op_produtivo


def _extrair(data_inicio: str, data_fim: str, **_):
    return extrair_op_produtivo(data_inicio, data_fim)


relatorio = RelatorioPronto(
    id="op_produtivo",
    nome="Produtivo por OP",
    descricao=(
        "Ordens de produção com apontamentos no período: status, tempos de "
        "produção/setup/parada, velocidade, peso produzido e consumido, lotes "
        "e tubetes. Baseado em SC2 + SH6 + SD4 + SB1 + SG2 + SH1 + SA1. Produção."
    ),
    filtros="periodo",
    extrair=_extrair,
)
