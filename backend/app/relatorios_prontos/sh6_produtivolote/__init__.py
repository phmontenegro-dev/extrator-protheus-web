"""
Registro do SH6 — Relatório Produtivo por Lote no sistema de auto-descoberta.

A função extrair_sh6_produtivolote aceita um parâmetro opcional `cliente`
que não é exposto no formulário atual (filtros="periodo"). Pra permitir que
um admin filtre por cliente no futuro sem quebrar o schema atual, a chamada
abaixo passa `cliente=None` implicitamente — a função usa o default. Quando
houver UI pra esse filtro, troque pra pegar `cliente` do kwargs recebido.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.sh6_produtivolote.extrair import extrair_sh6_produtivolote
from app.relatorios_prontos.sh6_produtivolote.tratar import tratar_dataframe


def _extrair(data_inicio: str, data_fim: str, **_):
    # O despachante central passa data_inicio/data_fim pros relatórios do tipo
    # "periodo". Outros kwargs (como "cliente" se vier do form no futuro) caem
    # em **_ — aqui passamos só o que a API do extrair aceita.
    return extrair_sh6_produtivolote(data_inicio, data_fim)


relatorio = RelatorioPronto(
    id="sh6_produtivolote",
    nome="SH6 — Relatório Produtivo por Lote",
    descricao="Relatório produtivo por lote",
    filtros="periodo",
    extrair=_extrair,
    tratar=tratar_dataframe,
)