"""
Registro do relatório pronto perfil_tributario no auto-descoberta (Etapa 11.6).
"""
from app.relatorios_prontos.base import RelatorioPronto
from app.relatorios_prontos.perfil_tributario.extrair import extrair_perfil_tributario


def _extrair(**_):
    return extrair_perfil_tributario()


relatorio = RelatorioPronto(
    id="perfil_tributario",
    nome="Perfil Tributário por Produto",
    descricao=(
        "Vínculo produto → perfil tributário (SB1 + F24 + F20): código e descrição "
        "do perfil atribuído a cada produto ativo. Fiscal."
    ),
    filtros="nenhum",
    extrair=_extrair,
)
