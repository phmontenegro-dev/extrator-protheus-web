"""
Extração do SB2 — Saldo Físico por Produto (Logística).

Dump completo de SB2010 com todas as colunas, filtrando apenas registros
não deletados. Para posição de estoque por armazém/produto.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sb2_saldo_fisico() -> pd.DataFrame:
    query = """
        SELECT s.*
        FROM SB2010 s
        WHERE s.D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
