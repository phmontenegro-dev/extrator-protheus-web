"""
Extração do SB6 — Saldo de Terceiros por Produto (Logística).

Dump de SB6010 — produtos em poder de/em posse de terceiros (remessas,
industrialização por encomenda etc). Todas as colunas, não deletados.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sb6_saldo_terceiros() -> pd.DataFrame:
    query = """
        SELECT s.*
        FROM SB6010 s
        WHERE s.D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
