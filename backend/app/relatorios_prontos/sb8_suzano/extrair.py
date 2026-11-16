"""
Extração do SB8 SUZANO — Saldos por Lote (SB8010).

Este relatório roda com filtros TOTALMENTE FIXOS, definidos pela regra de
negócio — não é parametrizável pelo usuário:
  - B8_SALDO > 1              (só saldos relevantes)
  - B8_LOTECTL LIKE '%SZ%'    (lotes Suzano)
  - D_E_L_E_T_ = ' '          (não deletados)

Se algum dia o critério mudar, ajustar aqui.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sb8_suzano() -> pd.DataFrame:
    query = """
        SELECT
            B8_FILIAL,
            B8_QTDORI,
            B8_PRODUTO,
            B8_LOCAL,
            B8_SALDO,
            B8_EMPENHO,
            B8_LOTECTL,
            B8_DOC,
            B8_DFABRIC
        FROM SB8010
        WHERE B8_SALDO > 1
          AND B8_LOTECTL LIKE '%SZ%'
          AND D_E_L_E_T_ = ' '
        ORDER BY B8_FILIAL, B8_PRODUTO, B8_LOTECTL
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()

    # Mantém códigos como texto (preserva zeros à esquerda).
    for col in ["B8_FILIAL", "B8_PRODUTO", "B8_LOCAL", "B8_LOTECTL", "B8_DOC"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
