"""
Consultas dinâmicas ao dicionário do Oracle:

  - listar_tabelas():  todas as tabelas visíveis ao usuário conectado,
                       opcionalmente filtradas pela regex FILTRO_NOMES_TABELAS.
  - listar_colunas():  colunas de uma tabela, na ordem original de definição,
                       já filtrando tipos binários/incompatíveis com CSV.

Sobre o filtro de tipos: RAW, LONG, BLOB, CLOB etc. podem conter bytes
arbitrários ou quebras de linha que corrompem o CSV (mesmo problema histórico
com CT2_KEY). Se precisar desses tipos, promover a extração a Relatório Pronto.
"""
import re
from typing import List

from app.oracle import get_oracle_connection
from app.relatorio_livre.config_tabelas import FILTRO_NOMES_TABELAS


# Tipos ocultados da lista de seleção do Relatório Livre.
TIPOS_OCULTOS = {
    "BLOB",
    "CLOB",
    "NCLOB",
    "RAW",
    "LONG RAW",
    "LONG",
    "BFILE",
}


def listar_tabelas() -> List[str]:
    """
    Retorna tabelas visíveis ao usuário conectado (via ALL_TABLES), em ordem
    alfabética, aplicando FILTRO_NOMES_TABELAS se definido.

    DISTINCT: a mesma tabela pode aparecer em vários schemas; para o Relatório
    Livre o nome é o que importa (o SELECT usa a resolução padrão: schema do
    usuário conectado primeiro, depois sinônimos).
    """
    conn = get_oracle_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT table_name FROM all_tables ORDER BY table_name")
        nomes = [linha[0] for linha in cur.fetchall()]
    finally:
        conn.close()

    if FILTRO_NOMES_TABELAS:
        padrao = re.compile(FILTRO_NOMES_TABELAS)
        nomes = [n for n in nomes if padrao.match(n)]

    return nomes


def listar_colunas(tabela: str) -> List[str]:
    """
    Colunas da tabela, na ordem de column_id, com tipos incompatíveis
    com CSV já removidos.

    GROUP BY: se a tabela existir em >1 schema, ALL_TAB_COLUMNS repete a
    coluna; mantemos uma entrada por nome usando a menor column_id como posição.
    """
    query = """
        SELECT column_name, MIN(data_type) AS data_type, MIN(column_id) AS pos
        FROM all_tab_columns
        WHERE table_name = :tab
        GROUP BY column_name
        ORDER BY pos
    """
    conn = get_oracle_connection()
    try:
        cur = conn.cursor()
        cur.execute(query, {"tab": tabela.upper()})
        linhas = cur.fetchall()
    finally:
        conn.close()

    return [
        nome
        for (nome, tipo, _pos) in linhas
        if (tipo or "").upper() not in TIPOS_OCULTOS
    ]
