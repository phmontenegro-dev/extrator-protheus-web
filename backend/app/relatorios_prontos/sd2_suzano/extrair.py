"""
Extração do SD2 SUZANO — Documentos de Saída (SD2010) com filtro Suzano.

Filtros fixos (não parametrizáveis pelo usuário):
  - D2_LOTECTL LIKE '%SZ%'    (lotes Suzano)
  - D_E_L_E_T_ = ' '          (não deletados)

Se o critério mudar, ajustar aqui.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sd2_suzano() -> pd.DataFrame:
    query = """
        SELECT
            D2_FILIAL,
            D2_COD,
            D2_UM,
            D2_QUANT,
            D2_TES,
            D2_CF,
            D2_CLIENTE,
            D2_LOCAL,
            D2_DOC,
            D2_LOTECTL,
            D2_TP,
            D2_EMISSAO
        FROM SD2010
        WHERE D2_LOTECTL LIKE '%SZ%'
          AND D_E_L_E_T_ = ' '
        ORDER BY D2_FILIAL, D2_COD, D2_LOTECTL
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    # Mantém códigos como texto (preserva zeros à esquerda).
    for col in ["D2_FILIAL", "D2_COD", "D2_UM", "D2_TES", "D2_CF",
                "D2_CLIENTE", "D2_LOCAL", "D2_DOC", "D2_LOTECTL", "D2_TP"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
