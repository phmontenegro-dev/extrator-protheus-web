"""
Extração do SB1 — Cadastro de Produtos (Logística).

Query literal fornecida pelo Pedro — traz TODAS as colunas de SB1010 dos
registros não deletados. É um dump do cadastro de produtos, útil como
insumo pra análises/cruzamentos externos.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sb1_produtos() -> pd.DataFrame:
    query = """
        SELECT s.*
        FROM SB1010 s
        WHERE s.D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
