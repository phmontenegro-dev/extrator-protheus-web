"""
Extração do SB8 — Extrato de Lotes (Logística).

Dump de SB8010 (controle por lote), filtrando saldo diferente de zero —
quem tem saldo 0 em geral não interessa pra conferência de estoque.

Query literal do Pedro — todas as colunas, não deletados.

Convive com `sb8_suzano`, que usa filtros fixos específicos (lote LIKE '%SZ%').
Aqui é a versão genérica.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sb8_extrato_lotes() -> pd.DataFrame:
    query = """
        SELECT s.*
        FROM SB8010 s
        WHERE s.B8_SALDO <> 0
          AND s.D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
