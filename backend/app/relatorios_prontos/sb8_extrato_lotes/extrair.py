"""
Extração do SB8 — Extrato de Lotes (Logística).

Dump de SB8010 (não deletados), filtrando saldo diferente de zero —
quem tem saldo 0 em geral não interessa pra conferência de estoque.
Colunas CSV-safe só — mesmo tratamento do SB1 (ver extrair.py do
sb1_produtos pro motivo).

Convive com `sb8_suzano`, que usa filtros fixos específicos (lote LIKE '%SZ%').
Aqui é a versão genérica.
"""
import pandas as pd

from app.oracle import get_oracle_connection
from app.relatorio_livre.consulta_colunas import nomes_colunas


def extrair_sb8_extrato_lotes() -> pd.DataFrame:
    colunas = nomes_colunas("SB8010")
    if not colunas:
        raise RuntimeError("SB8010 não tem colunas visíveis — verifique privilégios.")
    cols_sql = ", ".join(colunas)
    query = f"""
        SELECT {cols_sql}
        FROM SB8010
        WHERE B8_SALDO <> 0
          AND D_E_L_E_T_ = ' '
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
