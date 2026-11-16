"""
Extração do Relatório Consolidado Suzano - Jhon.

Consolida dados de bobinas produzidas (SH6010) com produto (SB1010) e pedido
do cliente (SC6010, via SUBSTR dos primeiros 6 caracteres da OP).

Filtros fixos (regra de negócio):
  - H6_LOTECTL LIKE '%SZ%'    (lotes Suzano)
  - D_E_L_E_T_ = ' '          (não deletados)

Filtro parametrizado (informado pelo usuário):
  - H6_DATAFIN BETWEEN :data_inicio AND :data_fim   (data fim do apontamento)
  Obs: H6_DATAFIN é USADO no filtro mas NÃO é retornado na projeção.

Os aliases já são definidos em português no SELECT (com aspas duplas para
o Oracle preservar caracteres especiais e maiúsculas/minúsculas).

TRIM aplicado em C6_NUMPCOM e C6_ITEMPC porque são CHAR de tamanho fixo
no Protheus — sem TRIM, o resultado ficaria com padding tipo 'PC12345    -01'.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_consolidado_suzano_jhon(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Parâmetros:
        data_inicio, data_fim: strings AAAAMMDD (filtro sobre H6_DATAFIN)
    """
    query = """
        SELECT
            H6.H6_XLOTELI AS "BOBINA MÃE",
            NULL AS "VOL.ID",
            H6.H6_XNUMBOB AS "BOBINA FILHA",
            H6.H6_XMETRO * 1000 AS "METRAGEM",
            B1.B1_XGRAM1 + B1.B1_XGRAM2 + B1.B1_XGRAM3 AS "GRAMATURA",
            H6.H6_XDIAM / 10 AS "DIAMETRO",
            H6.H6_XPESOB AS "PESO (KG)",
            H6.H6_XEMEND AS "EMENDAS",
            NULL AS "POSIÇÃO",
            H6.H6_XTIRA2 AS "TIRADA",
            H6.H6_LOTECTL AS "LOTE TECHNOCOAT",
            H6.H6_OP AS "NÚMERO DA OP",
            TRIM(C6.C6_NUMPCOM) || '-' || TRIM(C6.C6_ITEMPC) AS "PEDIDO DO CLIENTE"
        FROM SH6010 H6
            LEFT JOIN SB1010 B1
                ON B1.B1_COD = H6.H6_PRODUTO
                AND B1.D_E_L_E_T_ = ' '
            LEFT JOIN SC6010 C6
                ON C6.C6_NUM = SUBSTR(H6.H6_OP, 1, 6)
                AND C6.D_E_L_E_T_ = ' '
        WHERE H6.D_E_L_E_T_ = ' '
          AND H6.H6_LOTECTL LIKE '%SZ%'
          AND H6.H6_DATAFIN BETWEEN :data_inicio AND :data_fim
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

    # Preserva zeros à esquerda em códigos/textos.
    for col in ["BOBINA MÃE", "BOBINA FILHA", "LOTE TECHNOCOAT",
                "NÚMERO DA OP", "PEDIDO DO CLIENTE"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
