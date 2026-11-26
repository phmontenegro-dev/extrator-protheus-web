"""
Extração do SB1 — Cadastro de Produtos (Logística).

Dump do cadastro de produtos de SB1010 (não deletados), com todas as
colunas CSV-safe.

Por que não `SELECT s.*`: SB1010 na instalação do Pedro tem colunas
LONG/BLOB (ex.: B1_FOTO) que derrubavam a conexão em ~8s com
`InterfaceError: DPY-1001: not connected to database` dentro do
`pd.read_sql`. O fix é montar o SELECT dinâmico a partir do dicionário
Oracle, reaproveitando o mesmo filtro de tipos binários do Relatório
Livre (TIPOS_OCULTOS em consulta_colunas.py).
"""
import pandas as pd

from app.oracle import get_oracle_connection
from app.utils.colunas_oracle import nomes_colunas_safe


def extrair_sb1_produtos() -> pd.DataFrame:
    colunas = nomes_colunas_safe("SB1010")
    if not colunas:
        raise RuntimeError(
            "SB1010 não tem colunas visíveis ao usuário do banco — "
            "verifique privilégios de SELECT em ALL_TAB_COLUMNS."
        )
    cols_sql = ", ".join(colunas)
    query = f"""
        SELECT {cols_sql}
        FROM SB1010
        WHERE D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
