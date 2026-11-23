"""
Registro do relatório pronto consolidado_suzano_jhon no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.consolidado_suzano_jhon.extrair import extrair_consolidado_suzano_jhon
from app.relatorios_prontos.consolidado_suzano_jhon.tratar import tratar_dataframe


def _extrair(data_inicio: str, data_fim: str, **_):
    return extrair_consolidado_suzano_jhon(data_inicio, data_fim)


relatorio = RelatorioPronto(
    id='consolidado_suzano_jhon',
    nome='Relatório Consolidado Suzano - Jhon',
    descricao='Consolidação de bobinas (SH6+SB1+SC6) em layout custom, filtrada pela data fim do apontamento.',
    filtros='periodo',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
