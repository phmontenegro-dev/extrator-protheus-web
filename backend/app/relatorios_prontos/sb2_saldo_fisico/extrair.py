"""
Extração do SB2 — Saldo Físico por Produto (Logística).

Dump de SB2010 (não deletados) com todas as colunas CSV-safe.

Monta a lista a partir do dicionário Oracle e filtra LONG/BLOB/CLOB/RAW —
mesmo tratamento do SB1 (ver extrair.py do sb1_produtos pro motivo).
"""
import pandas as pd

from app.oracle import get_oracle_connection
from app.utils.colunas_oracle import nomes_colunas_safe


def extrair_sb2_saldo_fisico() -> pd.DataFrame:
    colunas = nomes_colunas_safe("SB2010")
    if not colunas:
        raise RuntimeError("SB2010 não tem colunas visíveis — verifique privilégios.")
    cols_sql = ", ".join(colunas)
    query = f"""
        SELECT {cols_sql}
        FROM SB2010
        WHERE D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
