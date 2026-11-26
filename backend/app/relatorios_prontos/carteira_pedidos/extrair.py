"""
Extração — Carteira de Pedidos (Logística).

Query fiel à versão do Pedro. Monta um mapa denormalizado da carteira a
partir de:
  - SC6010 (itens do pedido)
  - SC5010 (cabeçalho do pedido)
  - SA1010 / SA2010 (cliente — switch pelo tipo do pedido: 'B','D' = SA2 fornecedor)
  - SA3010 (vendedor)
  - SC2010 (OP relacionada ao item de pedido, sequência '001')
  - SC9010 (liberações, agregado por pedido+item: datas, qtd liberada,
    qtd bloqueada por crédito, qtd bloqueada por estoque)
  - SC2010 agregado (saldo de OPs em aberto por produto na filial)

Regras do WHERE externo:
  - C6 não deletado
  - Emissão do pedido ≥ -13 meses E ≤ '99991231' (janela de histórico)
  - OU: ainda tem saldo a atender (C6_QTDVEN - C6_QTDENT > 0) E não está
    bloqueado como resíduo eliminado (C6_BLQ ≠ 'R')

Como as colunas já saem com o nome final (aliases em UPPERCASE SNAKE), não
tem tratar.py — o DataFrame vai direto pro CSV.
"""
import pandas as pd

from app.oracle import get_oracle_connection


# SQL mantido LITERAL ao fornecido pelo Pedro — mudanças aqui devem
# preservar os aliases e a lógica dos JOINs, pois consumidores à jusante
# (planilhas, dashboards) dependem dos nomes das colunas.
_SQL = """
SELECT
    TRIM(C6.C6_FILIAL) AS FILIAL,
    TRIM(C6.C6_NUM) AS PEDIDO,
    TRIM(C6.C6_ITEM) AS ITEM,
    TRIM(C5.C5_TIPO) AS TIPO_PEDIDO,
    TRIM(C5.C5_CLIENTE) AS CLIENTE,
    TRIM(C5.C5_LOJACLI) AS LOJA,
    TRIM(CASE WHEN C5.C5_TIPO IN ('B', 'D') THEN A2.A2_NOME ELSE A1.A1_NOME END) AS NOME_CLIENTE,
    TRIM(CASE WHEN C5.C5_TIPO IN ('B', 'D') THEN A2.A2_MUN  ELSE A1.A1_MUN  END) AS MUNICIPIO_CLIENTE,
    TRIM(CASE WHEN C5.C5_TIPO IN ('B', 'D') THEN A2.A2_EST  ELSE A1.A1_EST  END) AS UF_CLIENTE,
    TRIM(C5.C5_VEND1) AS VENDEDOR,
    TRIM(A3.A3_NOME) AS NOME_VENDEDOR,
    TRIM(C5.C5_CONDPAG) AS COND_PAGAMENTO,
    TRIM(C5.C5_TPFRETE) AS TIPO_FRETE,
    TRIM(C6.C6_PEDCLI) AS PEDIDO_CLIENTE,
    TRIM(C6.C6_NUMPCOM) AS ORDEM_COMPRA,
    TRIM(C6.C6_ITEMPC) AS ITEM_ORDEM_COMPRA,
    TRIM(C6.C6_PRODUTO) AS PRODUTO,
    TRIM(C6.C6_DESCRI) AS DESCRICAO_PRODUTO,
    TRIM(C6.C6_UM) AS UNIDADE_MEDIDA,
    TRIM(C6.C6_SEGUM) AS SEGUNDA_UM,
    TRIM(C6.C6_LOCAL) AS ARMAZEM,
    TRIM(C6.C6_LOTECTL) AS LOTE_PEDIDO,
    TRIM(C6.C6_TES) AS TES,
    TRIM(C5.C5_EMISSAO) AS DT_EMISSAO,
    TRIM(C6.C6_ENTREG) AS DT_ENTREGA_SISTEMA,
    TRIM(C6.C6_DATFAT) AS DT_ULTIMO_FATURAMENTO_ITEM,
    TRIM(C6.C6_NOTA) AS ULTIMA_NF_ITEM,
    TRIM(C6.C6_SERIE) AS SERIE_ULTIMA_NF,
    LIB.DT_LIBERACAO AS DT_LIBERACAO,
    C6.C6_QTDVEN AS QTD_VENDIDA,
    C6.C6_QTDENT AS QTD_ATENDIDA,
    C6.C6_QTDVEN - C6.C6_QTDENT AS QTD_SALDO,
    C6.C6_UNSVEN AS QTD_VENDIDA_2UM,
    C6.C6_QTDEMP AS QTD_EMPENHADA,
    C6.C6_PRCVEN AS PRECO_UNITARIO,
    C6.C6_VALOR AS VALOR_ITEM,
    TRIM(C6.C6_BLQ) AS ELIMINADO_RESIDUO,
    NVL(LIB.QTD_LIBERADA, 0) AS QTD_LIBERADA,
    NVL(LIB.QTD_BLOQ_CREDITO, 0) AS QTD_BLOQ_CREDITO,
    NVL(LIB.QTD_BLOQ_ESTOQUE, 0) AS QTD_BLOQ_ESTOQUE,
    TRIM(C6.C6_NUMOP) AS OP_NUMERO,
    TRIM(C6.C6_ITEMOP) AS OP_ITEM,
    TRIM(C2.C2_EMISSAO) AS OP_DT_EMISSAO,
    TRIM(C2.C2_DATPRI) AS OP_DT_INICIO_PREVISTO,
    TRIM(C2.C2_DATPRF) AS OP_DT_FIM_PREVISTO,
    TRIM(C2.C2_DATRF) AS OP_DT_ENCERRAMENTO,
    C2.C2_QUANT AS OP_QTD_PREVISTA,
    C2.C2_QUJE AS OP_QTD_PRODUZIDA,
    NVL(OPA.QTD_OP_ABERTA, 0) AS QTD_OP_ABERTA_PRODUTO
FROM SC6010 C6
JOIN SC5010 C5
    ON C5.C5_FILIAL = C6.C6_FILIAL
   AND C5.C5_NUM    = C6.C6_NUM
   AND C5.D_E_L_E_T_ = ' '
LEFT JOIN (
    SELECT
        A1_COD,
        A1_LOJA,
        MAX(A1_NOME) AS A1_NOME,
        MAX(A1_MUN)  AS A1_MUN,
        MAX(A1_EST)  AS A1_EST
    FROM SA1010
    WHERE D_E_L_E_T_ = ' '
    GROUP BY A1_COD, A1_LOJA
) A1
    ON A1.A1_COD  = C5.C5_CLIENTE
   AND A1.A1_LOJA = C5.C5_LOJACLI
LEFT JOIN (
    SELECT
        A2_COD,
        A2_LOJA,
        MAX(A2_NOME) AS A2_NOME,
        MAX(A2_MUN)  AS A2_MUN,
        MAX(A2_EST)  AS A2_EST
    FROM SA2010
    WHERE D_E_L_E_T_ = ' '
    GROUP BY A2_COD, A2_LOJA
) A2
    ON A2.A2_COD  = C5.C5_CLIENTE
   AND A2.A2_LOJA = C5.C5_LOJACLI
   AND C5.C5_TIPO IN ('B', 'D')
LEFT JOIN (
    SELECT A3_COD, MAX(A3_NOME) AS A3_NOME
    FROM SA3010
    WHERE D_E_L_E_T_ = ' '
    GROUP BY A3_COD
) A3
    ON A3.A3_COD = C5.C5_VEND1
LEFT JOIN SC2010 C2
    ON C2.C2_FILIAL = C6.C6_FILIAL
   AND C2.C2_NUM    = C6.C6_NUMOP
   AND C2.C2_ITEM   = C6.C6_ITEMOP
   AND C2.C2_SEQUEN = '001'
   AND TRIM(C6.C6_NUMOP) IS NOT NULL
   AND C2.D_E_L_E_T_ = ' '
LEFT JOIN (
    SELECT
        C9_FILIAL,
        C9_PEDIDO,
        C9_ITEM,
        MIN(TRIM(C9_DATALIB)) AS DT_LIBERACAO,
        SUM(C9_QTDLIB)        AS QTD_LIBERADA,
        SUM(CASE WHEN NVL(TRIM(C9_BLCRED), '10') NOT IN ('10') THEN C9_QTDLIB ELSE 0 END) AS QTD_BLOQ_CREDITO,
        SUM(CASE WHEN NVL(TRIM(C9_BLEST),  '10') NOT IN ('10') THEN C9_QTDLIB ELSE 0 END) AS QTD_BLOQ_ESTOQUE
    FROM SC9010
    WHERE D_E_L_E_T_ = ' '
      AND TRIM(C9_NFISCAL) IS NULL
    GROUP BY C9_FILIAL, C9_PEDIDO, C9_ITEM
) LIB
    ON LIB.C9_FILIAL = C6.C6_FILIAL
   AND LIB.C9_PEDIDO = C6.C6_NUM
   AND LIB.C9_ITEM   = C6.C6_ITEM
LEFT JOIN (
    SELECT C2_FILIAL, C2_PRODUTO, SUM(C2_QUANT - C2_QUJE) AS QTD_OP_ABERTA
    FROM SC2010
    WHERE D_E_L_E_T_ = ' '
      AND TRIM(C2_DATRF) IS NULL
    GROUP BY C2_FILIAL, C2_PRODUTO
) OPA
    ON OPA.C2_FILIAL  = C6.C6_FILIAL
   AND OPA.C2_PRODUTO = C6.C6_PRODUTO
WHERE C6.D_E_L_E_T_ = ' '
  AND (
      C5.C5_EMISSAO BETWEEN TO_CHAR(ADD_MONTHS(TRUNC(SYSDATE, 'MM'), -13), 'YYYYMMDD')
                       AND '99991231'
      OR (
          SIGN(C6.C6_QTDVEN - C6.C6_QTDENT) = 1
          AND NVL(TRIM(C6.C6_BLQ), 'X') NOT IN ('R')
      )
  )
"""


def extrair_carteira_pedidos() -> pd.DataFrame:
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(_SQL, conn)
    finally:
        conn.close()
    return df
