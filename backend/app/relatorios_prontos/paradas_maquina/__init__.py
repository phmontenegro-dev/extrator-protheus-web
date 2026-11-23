"""
Registro do relatório pronto paradas_maquina no sistema de auto-descoberta (Etapa 11.6).

O backend varre app.relatorios_prontos.* no startup e encontra o `relatorio`
exportado aqui. Zero edição em routers ou runners pra adicionar/remover.

A lógica em si continua em `extrair.py` e `tratar.py`.
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.paradas_maquina.extrair import extrair_paradas_maquina
from app.relatorios_prontos.paradas_maquina.tratar import tratar_dataframe


def _extrair(data_inicio: str, data_fim: str, **_):
    return extrair_paradas_maquina(data_inicio, data_fim)


relatorio = RelatorioPronto(
    id='paradas_maquina',
    nome='Paradas de Máquina',
    descricao='Cruza eventos de parada (SH6) com a produção em andamento no mesmo recurso, por sobreposição temporal. Traz o motivo da parada (CYN), a OP afetada, o operador, duração em minutos e produto associado.',
    filtros='periodo',
    extrair=_extrair,
    tratar=tratar_dataframe,
)
