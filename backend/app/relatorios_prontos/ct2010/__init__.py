"""
Registro do relatório pronto ct2010 no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.ct2010.extrair import extrair_ct2010
from app.relatorios_prontos.ct2010.tratar import tratar_dataframe


def _extrair(data_inicio: str, data_fim: str, ctx=None, **_):
    # `ctx` chega do runner quando a extração roda dentro de um job
    # assíncrono — permite ao extrator bater heartbeat entre batches.
    # Fora de job (chamada síncrona antiga), vira None e não quebra nada.
    return extrair_ct2010(data_inicio, data_fim, ctx=ctx)


relatorio = RelatorioPronto(
    id='ct2010',
    nome='CT2010 — Lançamentos Contábeis',
    descricao='Lançamentos contábeis do período, com regras de partida dobrada, enriquecimento via Plano de Contas e Centro de Custo, e rastreamento da NF origem via CV3.',
    filtros='periodo',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
