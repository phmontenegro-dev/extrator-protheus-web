"""
Extração do SH6 SUZANO — Apontamentos de Produção (SH6010) com filtro Suzano.

Filtros fixos (regra de negócio):
  - H6_LOTECTL LIKE '%SZ%'    (lotes Suzano)
  - D_E_L_E_T_ = ' '          (não deletados)

Filtro parametrizado (informado pelo usuário):
  - H6_DTAPONT BETWEEN :data_inicio AND :data_fim   (data do apontamento)
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sh6_suzano(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Parâmetros:
        data_inicio, data_fim: strings AAAAMMDD (filtro sobre H6_DTAPONT)
    """
    query = """
        SELECT
            H6.H6_FILIAL,
            H6.H6_OP,
            H6.H6_PRODUTO,
            B1.B1_DESC,
            B1.B1_UM,
            H6.H6_RECURSO,
            H6.H6_DATAINI,
            H6.H6_HORAINI,
            H6.H6_DATAFIN,
            H6.H6_HORAFIN,
            H6.H6_QTDPROD,
            H6.H6_QTDPERD,
            H6.H6_DTAPONT,
            H6.H6_LOTECTL,
            H6.H6_DTPROD,
            H6.H6_LOCAL,
            H6.H6_XLOTELI,
            H6.H6_XDIAM,
            H6.H6_XNUMBOB
        FROM SH6010 H6
            INNER JOIN SB1010 B1
                ON B1.B1_COD = H6.H6_PRODUTO
                AND B1.D_E_L_E_T_ = ' '
        WHERE H6.H6_LOTECTL LIKE '%SZ%'
          AND H6.H6_DTAPONT BETWEEN :data_inicio AND :data_fim
          AND H6.D_E_L_E_T_ = ' '
        ORDER BY H6.H6_FILIAL, H6.H6_PRODUTO, H6.H6_LOTECTL
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
    for col in ["H6_FILIAL", "H6_OP", "H6_PRODUTO", "B1_UM", "H6_RECURSO",
                "H6_LOTECTL", "H6_LOCAL", "H6_XLOTELI", "H6_XNUMBOB"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
