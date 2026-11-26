"""
Extração do SD5 — Requisições de Lotes (Logística).

Dump de SD5010 — movimentos de lote com OP associada (D5_OP não vazio),
não deletados. Todas as colunas.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sd5_requisicoes_lotes() -> pd.DataFrame:
    query = """
        SELECT s.*
        FROM SD5010 s
        WHERE s.D5_OP <> ' '
          AND s.D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
