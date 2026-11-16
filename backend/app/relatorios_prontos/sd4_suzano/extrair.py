"""
Extração do SD4 SUZANO — Empenhos (SD4010) com filtro Suzano + período.

Filtros fixos (regra de negócio, não alteráveis pelo usuário):
  - D4_LOTECTL LIKE '%SZ%'    (lotes Suzano)
  - D_E_L_E_T_ = ' '          (não deletados)

Filtro parametrizado (informado pelo usuário na tela):
  - D4_EMPENHO BETWEEN :data_inicio AND :data_fim
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sd4_suzano(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Parâmetros:
        data_inicio, data_fim: strings AAAAMMDD (filtro sobre D4_EMPENHO)
    """
    query = """
        SELECT
            D4.D4_FILIAL,
            D4.D4_COD,
            B1.B1_UM,
            B1.B1_DESC,
            D4.D4_OP,
            D4.D4_LOCAL,
            D4.D4_DATA,
            D4.D4_QTDEORI,
            D4.D4_QUANT,
            D4.D4_SLDEMP,
            D4.D4_LOTECTL,
            D4.D4_PRODUTO,
            D4.D4_ROTEIRO,
            D4.D4_XLOTE
        FROM SD4010 D4
            INNER JOIN SB1010 B1
                ON B1.B1_COD = D4.D4_COD
                AND B1.D_E_L_E_T_ = ' '
        WHERE D4.D4_LOTECTL LIKE '%SZ%'
          AND D4.D4_EMPENHO BETWEEN :data_inicio AND :data_fim
          AND D4.D_E_L_E_T_ = ' '
        ORDER BY D4.D4_FILIAL, D4.D4_COD, D4.D4_LOTECTL
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(
            query,
            conn,
            params={"data_inicio": data_inicio, "data_fim": data_fim},
        )
    finally:
        conn.close()

    # Mantém códigos como texto (preserva zeros à esquerda).
    for col in ["D4_FILIAL", "D4_COD", "B1_UM", "D4_OP", "D4_LOCAL",
                "D4_LOTECTL", "D4_PRODUTO", "D4_ROTEIRO", "D4_XLOTE"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
