"""Extração do relatório produtivo por lote da filial 0101001."""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_sh6_produtivolote(
    data_inicio: str,
    data_fim: str,
    cliente: str | None = None,
) -> pd.DataFrame:
    query = """
        SELECT
            B8.B8_FILIAL AS FILIAL,
            D1.D1_FORNECE AS FORNECEDOR,
            D2.D2_CLIENTE AS CLIENTE,
            A1.A1_NOME AS NOME_CLIENTE,
            D2.D2_LOJA AS LOJA,
            B8.B8_PRODUTO AS COD_PRODUTO,
            B1.B1_TIPO AS TIPO_PRODUTO,
            B1.B1_DESC AS DESCRICAO_PROD,
            B1.B1_UM AS UNIDADE_MEDIDA,
            B8.B8_LOCAL AS ARMAZEM,
            BF.BF_LOCALIZ AS ENDERECO,
            D1.D1_QUANT AS QNTD_RECEBIDA,
            B8.B8_SALDO AS QNTD_DO_LOTE,
            NVL(EMP.QTD_EMPENHO, 0) AS QNTD_EMPENHO,
            B8.B8_QTDORI AS QNTD_ORIGINAL,
            H6.H6_OP AS OP,
            CASE
                WHEN TRIM(H6.H6_DATAINI) IS NOT NULL
                 AND TRIM(H6.H6_HORAINI) IS NOT NULL
                 AND TRIM(H6.H6_DATAFIN) IS NOT NULL
                 AND TRIM(H6.H6_HORAFIN) IS NOT NULL THEN 'FECHADA'
                WHEN TRIM(H6.H6_DATAINI) IS NOT NULL
                 AND TRIM(H6.H6_HORAINI) IS NOT NULL
                 AND (
                     TRIM(H6.H6_DATAFIN) IS NULL
                     OR TRIM(H6.H6_HORAFIN) IS NULL
                 ) THEN 'ABERTA'
            END AS STATUS_OP,
            C2.C2_DATPRI AS DATA_PREV_INICIO,
            C2.C2_DATPRF AS DATA_PREV_FINAL,
            D4.D4_OPORIG AS OP_PAI,
            D4.D4_PRODUTO AS PRODUTO_PAI,
            B8.B8_LOTECTL AS LOTE,
            H6.H6_XLOTELI AS LOTE_LIDO,
            H6.H6_XNUMBOB AS BOBINA_02A,
            H6.H6_RECURSO AS RECURSO,
            H1.H1_DESCRI AS DESC_RECURSO,
            H6.H6_OPERAC AS OPERACAO,
            VI.VI_DESCRI AS DESC_OPERACAO,
            D4.D4_ROTEIRO AS ROTEIRO,
            CASE TRIM(D4.D4_ROTEIRO)
                WHEN '1' THEN 'Produção Padrão'
                WHEN '2' THEN 'Retrabalho Rebobinamento'
                WHEN '3' THEN 'Retrabalho Corona'
            END AS DESC_ROTEIRO,
            H6.H6_OPERADO AS OPERADOR,
            H6.H6_DTAPONT AS DATA_APONT,
            CASE WHEN TRIM(H6.H6_DATAINI) IS NOT NULL THEN
                TRIM(H6.H6_DATAINI) || ' ' || TRIM(H6.H6_HORAINI)
            END AS DATA_HORA_INICIAL,
            CASE WHEN TRIM(H6.H6_DATAFIN) IS NOT NULL THEN
                TRIM(H6.H6_DATAFIN) || ' ' || TRIM(H6.H6_HORAFIN)
            END AS DATA_HORA_FINAL,
            H6.H6_TEMPO AS TEMPO_REAL,
            H6.H6_QTDPROD AS QNTD_PRODUZIDA,
            H6.H6_QTDPERD AS QNTD_PERDA,
            H6.H6_XPESOB AS PESO_BRUTO,
            H6.H6_XPESOL AS PESO_LIQUIDO,
            CASE B1.B1_UM
                WHEN 'KG' THEN NVL(H6.H6_XPESOB, 0) / 1000
                WHEN 'FL' THEN NVL(H6.H6_QTDPRO2, 0)
                ELSE 0
            END AS PESO_BRUTO_TON,
            CASE B1.B1_UM
                WHEN 'KG' THEN NVL(H6.H6_XPESOL, 0) / 1000
                WHEN 'FL' THEN NVL(H6.H6_QTDPRO2, 0)
                ELSE 0
            END AS PESO_LIQUIDO_TON,
            H6.H6_XDIAM AS DIAMETRO,
            H6.H6_XMETRO AS METRAGEM,
            H6.H6_XMTQUA AS M2,
            H6.H6_XEMEND AS EMENDAS,
            H6.H6_XTIRA2 AS TIRADAS,
            CASE B1.B1_UM WHEN 'FL' THEN 'FOLHA' ELSE 'BOBINA' END AS FOLHA_BOBINA,
            B1LI.B1_XLARG AS LARGURA_LOTELID,
            NVL(B1LI.B1_XGRAM1, 0) + NVL(B1LI.B1_XGRAM2, 0)
                + NVL(B1LI.B1_XGRAM3, 0) AS GRAMATURA_LOTELIDO,
            B1LI.B1_XGRAM1 AS GRAM_PE1_LOTELIDO,
            B1LI.B1_XGRAM2 AS GRAM_PE2_LOTELIDO,
            B1LI.B1_XGRAM3 AS GRAM_PE3_LOTELIDO,
            B1.B1_XLARG AS LARGURA_FINAL,
            B1.B1_XCOMP AS COMPRIMENTO,
            NVL(B1.B1_XGRAM1, 0) + NVL(B1.B1_XGRAM2, 0)
                + NVL(B1.B1_XGRAM3, 0) AS GRAMATURA,
            B1.B1_XGRAM1 AS GRAM_PE1,
            B1.B1_XGRAM2 AS GRAM_PE2,
            B1.B1_XGRAM3 AS GRAM_PE3,
            D2.D2_QUANT AS QNTD_FATURADA,
            D2.D2_EMISSAO AS DATA_EMISSAO,
            D2.D2_TOTAL AS VALOR_VENDA,
            D2.D2_PEDIDO AS PEDIDO_VENDA,
            D2.D2_DOC AS NF_SAIDA,
            D2.D2_ITEMPV AS ITEM_NF_SAIDA,
            D2.D2_SERIE AS SERIE_NF_SAIDA,
            D2.D2_CF AS CODIGO_FISCAL,
            D2.D2_CUSTO1 AS CUSTO,
            CASE WHEN TRIM(C6.C6_NUM) IS NOT NULL THEN
                RTRIM(C6.C6_NUM) || '/' || RTRIM(C6.C6_ITEM)
            END AS PEDIDO_ITEM_COMPRA_SUZ,
            D1.D1_TIPO AS TIPO_ENTRADA,
            D1.D1_PEDIDO AS PEDIDO_COMPRA,
            D1.D1_DOC AS NF_ENTRADA,
            D1.D1_EMISSAO AS DATA_EMISSAO_ENTRADA
        FROM SB8010 B8
        LEFT JOIN SB1010 B1
            ON B1.B1_COD = B8.B8_PRODUTO
           AND B1.D_E_L_E_T_ = ' '
        LEFT JOIN SBF010 BF
            ON BF.BF_FILIAL = B8.B8_FILIAL
           AND BF.BF_PRODUTO = B8.B8_PRODUTO
           AND BF.BF_LOCAL = B8.B8_LOCAL
           AND BF.BF_LOTECTL = B8.B8_LOTECTL
           AND BF.D_E_L_E_T_ = ' '
        LEFT JOIN SD1010 D1
            ON D1.D1_FILIAL = B8.B8_FILIAL
           AND D1.D1_COD = B8.B8_PRODUTO
           AND D1.D1_LOTECTL = B8.B8_LOTECTL
           AND D1.D_E_L_E_T_ = ' '
        LEFT JOIN SD2010 D2
            ON D2.D2_FILIAL = B8.B8_FILIAL
           AND D2.D2_COD = B8.B8_PRODUTO
           AND D2.D2_LOTECTL = B8.B8_LOTECTL
           AND D2.D_E_L_E_T_ = ' '
        LEFT JOIN SD4010 D4
            ON D4.D4_FILIAL = B8.B8_FILIAL
           AND D4.D4_COD = B8.B8_PRODUTO
           AND D4.D4_LOTECTL = B8.B8_LOTECTL
           AND D4.D_E_L_E_T_ = ' '
        LEFT JOIN SH6010 H6
            ON H6.H6_FILIAL = B8.B8_FILIAL
           AND H6.H6_PRODUTO = B8.B8_PRODUTO
           AND H6.H6_LOTECTL = B8.B8_LOTECTL
           AND H6.D_E_L_E_T_ = ' '
        LEFT JOIN SC2010 C2
            ON C2.C2_FILIAL = H6.H6_FILIAL
           AND RTRIM(C2.C2_NUM) || RTRIM(C2.C2_ITEM) || RTRIM(C2.C2_SEQUEN)
               = RTRIM(H6.H6_OP)
           AND C2.D_E_L_E_T_ = ' '
        LEFT JOIN SH1010 H1
            ON H1.H1_FILIAL = H6.H6_FILIAL
           AND H1.H1_CODIGO = H6.H6_RECURSO
           AND H1.D_E_L_E_T_ = ' '
        LEFT JOIN SVI010 VI
            ON VI.VI_FILIAL = H6.H6_FILIAL
           AND VI.VI_CODIGO = H6.H6_OPERAC
           AND VI.D_E_L_E_T_ = ' '
        LEFT JOIN SA1010 A1
            ON A1.A1_COD = D2.D2_CLIENTE
           AND A1.A1_LOJA = D2.D2_LOJA
           AND A1.D_E_L_E_T_ = ' '
        LEFT JOIN SC6010 C6
            ON C6.C6_LOTECTL = B8.B8_LOTECTL
           AND C6.D_E_L_E_T_ = ' '
        LEFT JOIN SB8010 B8LI
            ON B8LI.B8_FILIAL = H6.H6_FILIAL
           AND B8LI.B8_LOTECTL = H6.H6_XLOTELI
           AND B8LI.D_E_L_E_T_ = ' '
        LEFT JOIN SB1010 B1LI
            ON B1LI.B1_COD = B8LI.B8_PRODUTO
           AND B1LI.D_E_L_E_T_ = ' '
        LEFT JOIN (
            SELECT D4_FILIAL, D4_COD, D4_LOTECTL, SUM(D4_QUANT) AS QTD_EMPENHO
            FROM SD4010
            WHERE D_E_L_E_T_ = ' '
            GROUP BY D4_FILIAL, D4_COD, D4_LOTECTL
        ) EMP
            ON EMP.D4_FILIAL = B8.B8_FILIAL
           AND EMP.D4_COD = B8.B8_PRODUTO
           AND EMP.D4_LOTECTL = B8.B8_LOTECTL
        WHERE B8.D_E_L_E_T_ = ' '
          AND B8.B8_FILIAL = :filial
          AND (:cliente IS NULL OR RTRIM(D2.D2_CLIENTE) = :cliente)
          AND NVL(LTRIM(B1.B1_DESC), 'X') NOT LIKE 'POLIETILENO%'
          AND (
              C2.C2_DATPRI BETWEEN :data_inicio AND :data_fim
              OR C2.C2_DATPRF BETWEEN :data_inicio AND :data_fim
              OR H6.H6_DTAPONT BETWEEN :data_inicio AND :data_fim
              OR H6.H6_DATAINI BETWEEN :data_inicio AND :data_fim
              OR H6.H6_DATAFIN BETWEEN :data_inicio AND :data_fim
              OR D2.D2_EMISSAO BETWEEN :data_inicio AND :data_fim
              OR D1.D1_EMISSAO BETWEEN :data_inicio AND :data_fim
          )
        ORDER BY B8.B8_FILIAL, B8.B8_PRODUTO, B8.B8_LOTECTL,
                 H6.H6_DATAINI, H6.H6_HORAINI
    """
    params = {
        "filial": "0101001",
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "cliente": (cliente or "").strip() or None,
    }
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn, params=params, coerce_float=False)
    finally:
        conn.close()

    for col in (
        "FILIAL", "FORNECEDOR", "CLIENTE", "LOJA", "COD_PRODUTO",
        "TIPO_PRODUTO", "UNIDADE_MEDIDA", "ARMAZEM", "ENDERECO",
        "OP", "OP_PAI", "PRODUTO_PAI", "LOTE", "LOTE_LIDO", "BOBINA_02A",
        "RECURSO", "OPERACAO", "ROTEIRO", "OPERADOR", "PEDIDO_VENDA",
        "NF_SAIDA", "ITEM_NF_SAIDA", "SERIE_NF_SAIDA", "CODIGO_FISCAL",
        "PEDIDO_ITEM_COMPRA_SUZ", "TIPO_ENTRADA", "PEDIDO_COMPRA", "NF_ENTRADA",
    ):
        df[col] = df[col].fillna("").astype(str).str.strip()

    return df