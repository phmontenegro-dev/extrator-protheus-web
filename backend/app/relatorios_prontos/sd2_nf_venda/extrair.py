"""
Extração do SD2 — Notas Fiscais de Venda (Logística).

Query fiel à versão do Pedro:
  - Colunas renomeadas pro português na SELECT (CSV sai com cabeçalho legível)
  - D2_QUANT e D2_TOTAL formatados pra padrão BR (vírgula decimal) via TO_CHAR+REPLACE
  - D2_EMISSAO convertido pra DD/MM/YYYY
  - Filtro de janela: emissão a partir do mês -13 meses (relativo a SYSDATE)
    até '99991231' (ou seja: últimos 13 meses em diante)

Como o SELECT já formata tudo, não existe tratar.py — o DataFrame vai direto
pro CSV.
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sd2_nf_venda() -> pd.DataFrame:
    query = """
        SELECT
            TRIM(D2_FILIAL) AS "Filial",
            TRIM(D2_COD) AS "Produto",
            REPLACE(RTRIM(TO_CHAR(D2_QUANT, 'FM9999999990.999999'), '.'), '.', ',') AS "Quantidade",
            TRIM(D2_CF) AS "Cod. Fiscal",
            TO_CHAR(TO_DATE(D2_EMISSAO, 'YYYYMMDD'), 'DD/MM/YYYY') AS "Emissao",
            TRIM(D2_DOC) AS "Num. Docto.",
            TRIM(D2_SERIE) AS "Serie",
            TRIM(D2_ITEM) AS "Item NF",
            TRIM(D2_PEDIDO) AS "Pedido",
            TRIM(D2_ITEMPV) AS "Item Pedido",
            TRIM(D2_CLIENTE) AS "Cliente",
            TRIM(D2_LOJA) AS "Loja",
            TRIM(D2_LOTECTL) AS "Lote",
            REPLACE(RTRIM(TO_CHAR(D2_TOTAL, 'FM9999999990.99'), '.'), '.', ',') AS "Valor"
        FROM SD2010
        WHERE D_E_L_E_T_ = ' '
          AND D2_EMISSAO BETWEEN TO_CHAR(ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -13), 'YYYYMMDD')
                            AND '99991231'
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn)
    finally:
        conn.close()
    return df
