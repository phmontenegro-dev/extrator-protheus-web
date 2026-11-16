"""
Extração do SD1 SUZANO — Documentos de Entrada (SD1010) com filtro Suzano.

Filtros fixos (não parametrizáveis pelo usuário):
  - D1_LOTECTL LIKE '%SZ%'    (lotes Suzano)
  - D_E_L_E_T_ = ' '          (não deletados)

Se o critério mudar, ajustar aqui.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sd1_suzano() -> pd.DataFrame:
    query = """
        SELECT
            D1_FILIAL,
            D1_COD,
            D1_XDESCPR,
            D1_UM,
            D1_QUANT,
            D1_LOTECTL,
            D1_DOC,
            D1_EMISSAO,
            D1_DTDIGIT
        FROM SD1010
        WHERE D1_LOTECTL LIKE '%SZ%'
          AND D_E_L_E_T_ = ' '
        ORDER BY D1_FILIAL, D1_COD, D1_LOTECTL
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    # Mantém códigos como texto (preserva zeros à esquerda).
    for col in ["D1_FILIAL", "D1_COD", "D1_UM", "D1_LOTECTL", "D1_DOC"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
