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
from typing import List, TypedDict

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


class ColunaInfo(TypedDict):
    """
    Metadata de uma coluna. `tipo_oracle` é o nome bruto do Oracle
    (NUMBER, VARCHAR2, DATE, TIMESTAMP, CHAR...). `tipo_logico` é a
    categoria usada pelo frontend pra decidir que operadores mostrar:
    "texto" | "numero" | "data".
    """
    nome: str
    tipo_oracle: str
    tipo_logico: str


# Mapeamento Oracle → categoria lógica usada no frontend.
_TIPOS_NUMERICOS = {"NUMBER", "FLOAT", "BINARY_FLOAT", "BINARY_DOUBLE", "INTEGER"}
_TIPOS_DATA = {"DATE", "TIMESTAMP"}


def _categorizar(tipo_oracle: str) -> str:
    """
    Devolve 'numero' | 'data' | 'texto' baseado no tipo Oracle.
    Qualquer coisa que não seja número ou data cai em 'texto' (varchar,
    nvarchar, char, etc).
    """
    t = (tipo_oracle or "").upper()
    if t in _TIPOS_NUMERICOS:
        return "numero"
    if t in _TIPOS_DATA or t.startswith("TIMESTAMP"):
        return "data"
    return "texto"


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


def listar_colunas(tabela: str) -> List[ColunaInfo]:
    """
    Colunas da tabela, na ordem de column_id, com tipos incompatíveis
    com CSV já removidos.

    Devolve dicts com nome, tipo bruto do Oracle e categoria lógica
    ("texto" | "numero" | "data") — o frontend usa essa categoria pra
    escolher os operadores corretos nos filtros dinâmicos.

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

    resultado: List[ColunaInfo] = []
    for nome, tipo, _pos in linhas:
        tipo_up = (tipo or "").upper()
        if tipo_up in TIPOS_OCULTOS:
            continue
        resultado.append({
            "nome": nome,
            "tipo_oracle": tipo_up,
            "tipo_logico": _categorizar(tipo_up),
        })
    return resultado


def nomes_colunas(tabela: str) -> List[str]:
    """Helper de compat com código legado que só queria a lista de nomes."""
    return [c["nome"] for c in listar_colunas(tabela)]
