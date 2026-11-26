"""
Extração do SD5 — Requisições de Lotes (Logística).

Dump de SD5010 — movimentos de lote com OP associada (D5_OP não vazio),
não deletados. Colunas CSV-safe só — mesmo tratamento do SB1 (ver
extrair.py do sb1_produtos pro motivo).
"""
import pandas as pd

from app.oracle import get_oracle_connection
from app.utils.colunas_oracle import nomes_colunas_safe


def extrair_sd5_requisicoes_lotes() -> pd.DataFrame:
    colunas = nomes_colunas_safe("SD5010")
    if not colunas:
        raise RuntimeError("SD5010 não tem colunas visíveis — verifique privilégios.")
    cols_sql = ", ".join(colunas)
    query = f"""
        SELECT {cols_sql}
        FROM SD5010
        WHERE D5_OP <> ' '
          AND D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
