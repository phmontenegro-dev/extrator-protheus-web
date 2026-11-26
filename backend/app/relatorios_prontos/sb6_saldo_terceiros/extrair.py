"""
Extração do SB6 — Saldo de Terceiros por Produto (Logística).

Dump de SB6010 (não deletados) com todas as colunas CSV-safe — mesmo
tratamento do SB1 (ver extrair.py do sb1_produtos pro motivo).
"""
import pandas as pd

from app.oracle import get_oracle_connection
from app.utils.colunas_oracle import nomes_colunas_safe


def extrair_sb6_saldo_terceiros() -> pd.DataFrame:
    colunas = nomes_colunas_safe("SB6010")
    if not colunas:
        raise RuntimeError("SB6010 não tem colunas visíveis — verifique privilégios.")
    cols_sql = ", ".join(colunas)
    query = f"""
        SELECT {cols_sql}
        FROM SB6010
        WHERE D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
