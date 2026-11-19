"""
Cadastro central dos relatórios prontos disponíveis na web.

Cada entrada tem metadata (id, nome exibível, descrição, tipo de filtros).
O campo `filtros` é usado pelo frontend para renderizar o formulário certo
de cada relatório, de forma genérica. Valores possíveis:

  - "nenhum"      : nenhum filtro (só botão Extrair). Ex: SB8/SD1/SD2 Suzano.
  - "periodo"     : data_inicio + data_fim. Maioria.
  - "filial_periodo": filial + data_inicio + data_fim. Ex: QPR010.

Para adicionar um novo relatório pronto:
  1. Criar app/relatorios_prontos/<id>/ com extrair.py + tratar.py
  2. Registrar aqui
  3. Adicionar o endpoint em routers/relatorios.py
"""
from typing import Literal, TypedDict


TipoFiltro = Literal["nenhum", "periodo", "filial_periodo", "livre", "sql"]


class RelatorioInfo(TypedDict):
    id: str
    nome: str
    descricao: str
    filtros: TipoFiltro


RELATORIOS: list[RelatorioInfo] = [
    {
        "id": "ct2010",
        "nome": "CT2010 — Lançamentos Contábeis",
        "descricao": (
            "Lançamentos contábeis do período, com regras de partida dobrada, "
            "enriquecimento via Plano de Contas e Centro de Custo, e rastreamento "
            "da NF origem via CV3."
        ),
        "filtros": "periodo",
    },
    {
        "id": "qpr010",
        "nome": "QPR010 — Medições de Qualidade",
        "descricao": (
            "Medições de qualidade (QPR) com joins em QPS/QPQ/QPL/SH6/SB1/QP1/QP7/QAA, "
            "consolidando data+hora, lote final, bobina filha e dedup por lote+ensaio."
        ),
        "filtros": "filial_periodo",
    },
    {
        "id": "sft010",
        "nome": "SFT010 — Documentos de Entrada e Saída",
        "descricao": (
            "Documentos fiscais (SFT) com cliente/fornecedor, grupo, custos e duas "
            "fotos de estoque (SB9) nos meses de contorno do período."
        ),
        "filtros": "periodo",
    },
    {
        "id": "sd3010",
        "nome": "SD3010 — Movimentações Internas",
        "descricao": "Movimentações internas de estoque vinculadas a OP, com produto e grupo.",
        "filtros": "periodo",
    },
    {
        "id": "sb8_suzano",
        "nome": "SB8 SUZANO — Saldos por Lote",
        "descricao": "Saldos de estoque com lote Suzano (filtros fixos: saldo > 1 + lote %SZ%).",
        "filtros": "nenhum",
    },
    {
        "id": "sd1_suzano",
        "nome": "SD1 SUZANO — Documentos de Entrada",
        "descricao": "Documentos de entrada com lote Suzano (sem parâmetros).",
        "filtros": "nenhum",
    },
    {
        "id": "sd2_suzano",
        "nome": "SD2 SUZANO — Documentos de Saída",
        "descricao": "Documentos de saída com lote Suzano (sem parâmetros).",
        "filtros": "nenhum",
    },
    {
        "id": "sd4_suzano",
        "nome": "SD4 SUZANO — Empenhos",
        "descricao": "Empenhos de insumo com lote Suzano, filtrados pela data de empenho.",
        "filtros": "periodo",
    },
    {
        "id": "sh6_suzano",
        "nome": "SH6 SUZANO — Apontamentos de Produção",
        "descricao": "Apontamentos de produção com lote Suzano, filtrados pela data de apontamento.",
        "filtros": "periodo",
    },
    {
        "id": "consolidado_suzano_jhon",
        "nome": "Relatório Consolidado Suzano - Jhon",
        "descricao": (
            "Consolidação de bobinas (SH6+SB1+SC6) em layout custom, filtrada "
            "pela data fim do apontamento."
        ),
        "filtros": "periodo",
    },
    {
        "id": "paradas_maquina",
        "nome": "Paradas de Máquina",
        "descricao": (
            "Cruza eventos de parada (SH6) com a produção em andamento no "
            "mesmo recurso, por sobreposição temporal. Traz o motivo da "
            "parada (CYN), a OP afetada, o operador, duração em minutos e "
            "produto associado."
        ),
        "filtros": "periodo",
    },


    {
        "id": "sh6_produtivolote",
        "nome": "SH6 - Relatório Produtivo por Lote",
        "descricao": "Relatório produtivo por lote.",
        "filtros": "periodo",
    },



    # Relatório Livre não é um "relatório pronto" — é uma ferramenta de
    # extração ad hoc. Fica no registry por conveniência: aparece no menu,
    # no sistema de permissões e nos logs igual aos outros, mas tem rota
    # própria (/relatorio-livre/*) em vez de /relatorios/<id>/extrair.
    {
        "id": "relatorio_livre",
        "nome": "Relatório Livre",
        "descricao": (
            "Extração crua de qualquer tabela do Protheus — escolha a tabela, "
            "as colunas desejadas e opcionalmente um período de datas."
        ),
        "filtros": "livre",
    },
    # Código SQL — mesma lógica do Relatório Livre, mas pra executar SELECT
    # direto. Rota própria em /sql-livre/*. Super restrito: validador recusa
    # tudo que não seja SELECT, timeout curto, só quem for admin ou tiver
    # permissão explícita.
    {
        "id": "codigo_sql",
        "nome": "Código SQL",
        "descricao": (
            "Execute consultas SELECT livres no Oracle Protheus. "
            "Ferramenta avançada para administradores — bloqueia qualquer "
            "comando que não seja de leitura."
        ),
        "filtros": "sql",
    },
]


def existe(relatorio_id: str) -> bool:
    return any(r["id"] == relatorio_id for r in RELATORIOS)


def buscar(relatorio_id: str) -> RelatorioInfo | None:
    for r in RELATORIOS:
        if r["id"] == relatorio_id:
            return r
    return None
