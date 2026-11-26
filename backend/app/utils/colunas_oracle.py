"""
Helper neutro pra consultar metadata de colunas Oracle sem arrastar
dependência de outros módulos do app (relatorio_livre, etc).

Serve principalmente aos extratores de "relatórios prontos" que fazem
dump de tabela inteira: eles precisam listar colunas sem tipos binários
pra evitar `SELECT s.*` esbarrar em BLOB/LONG e derrubar a conexão com
`DPY-1001` no python-oracledb.

Se precisar da versão "rica" (com tipo lógico pra UI dinâmica), olhe
`app.relatorio_livre.consulta_colunas.listar_colunas()` — ela faz a mesma
coisa e mais, mas pertence à stack do Relatório Livre.
"""
from typing import List

from app.oracle import get_oracle_connection


# Tipos que causam problemas em CSV / fetch via pandas e são ignorados
# nos dumps full. Mantido em sincronia com TIPOS_OCULTOS do Relatório Livre.
TIPOS_INCOMPATIVEIS = {
    "BLOB",
    "CLOB",
    "NCLOB",
    "RAW",
    "LONG RAW",
    "LONG",
    "BFILE",
}


def nomes_colunas_safe(tabela: str) -> List[str]:
    """
    Nomes das colunas de `tabela` em ordem de column_id, excluindo tipos
    binários / incompatíveis com CSV.

    GROUP BY: se a tabela existir em mais de 1 schema, ALL_TAB_COLUMNS
    duplica a coluna; mantemos uma entrada por nome usando MIN(column_id)
    como posição (igual ao que o Relatório Livre já faz).
    """
    query = """
        SELECT column_name,
               MIN(data_type) AS data_type,
               MIN(column_id) AS pos
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
        if (tipo or "").upper() not in TIPOS_INCOMPATIVEIS
    ]
