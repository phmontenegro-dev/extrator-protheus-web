"""
Extração — Produtivo por OP (Produção).

Query fiel à versão do Pedro. Monta um mapa denormalizado por Ordem de
Produção a partir de:
  - SC2010 (ordens de produção)
  - SH6010 (apontamentos de produção e paradas de máquina)
  - SD4010 (empenhos / consumo)
  - SB1010 (cadastro de produto — unidade, gramatura, dimensões)
  - SG2010 (operações do roteiro)
  - SH1010 (recursos)
  - SA1010 (clientes)

A única mudança em relação ao SQL fornecido pelo Pedro é a CTE
`Parametros`, que ali tinha as datas hardcoded (`DATE '2026-11-19'`) e
aqui recebe bind variables `:data_inicio` e `:data_fim` convertidas
via TO_DATE a partir do formato AAAAMMDD (padrão de datas do sistema).

Como o SELECT já formata hora/data, valores em TN e strings de tempo
HHH:MM, não tem `tratar.py` — o DataFrame vai direto pro CSV.
"""
import pandas as pd

from app.oracle import get_oracle_connection


# SQL mantido LITERAL ao fornecido pelo Pedro — mudanças aqui devem
# preservar os aliases e a lógica dos JOINs/OUTER APPLYs, pois consumidores
# à jusante (planilhas, dashboards) dependem dos nomes das colunas.
_SQL = """
WITH Parametros AS (
    SELECT TO_DATE(:data_inicio, 'YYYYMMDD') AS DataInicial,
           TO_DATE(:data_fim,    'YYYYMMDD') AS DataFinal
    FROM dual
),
Ordens AS (
    SELECT C2_FILIAL AS Filial, C2_OP AS OP, C2_PRODUTO AS Produto,
           C2_ROTEIRO AS Roteiro, C2_XRECURS AS Recurso,
           C2_XCLIENT AS Cliente, C2_XLOJA AS LojaCliente,
           TO_DATE(TRIM(C2_DATPRI) DEFAULT NULL ON CONVERSION ERROR,
                   'FXYYYYMMDD') AS DataPrevista,
           C2_QUANT AS QuantidadePrevista
    FROM SC2010
    WHERE D_E_L_E_T_ = ' ' AND TRIM(C2_OP) IS NOT NULL
    -- AND C2_FILIAL = '01'
    -- AND C2_OP = '00012301001'
),
Produtos AS (
    SELECT TRIM(B1_FILIAL) AS Filial, B1_COD AS Codigo,
           TRIM(B1_UM) AS UM, RTRIM(B1_DESC) AS Descricao,
           B1_XLARG AS Largura, B1_XCOMP AS Comprimento,
           NVL(B1_XGRAM1, 0) + NVL(B1_XGRAM2, 0) + NVL(B1_XGRAM3, 0) AS Gramatura,
           R_E_C_N_O_ AS Recno
    FROM SB1010
    WHERE D_E_L_E_T_ = ' '
),
DatasPorOP AS (
    SELECT H.H6_FILIAL AS Filial, H.H6_OP AS OP,
           MIN(TO_DATE(TRIM(H.H6_DATAINI) DEFAULT NULL ON CONVERSION ERROR,
                       'FXYYYYMMDD')) AS DataInicio,
           MAX(TO_DATE(TRIM(H.H6_DATAFIN) DEFAULT NULL ON CONVERSION ERROR,
                       'FXYYYYMMDD')) AS DataFim
    FROM SH6010 H
    CROSS JOIN Parametros F
    WHERE H.D_E_L_E_T_ = ' '
      AND (F.DataInicial IS NOT NULL OR F.DataFinal IS NOT NULL)
      AND EXISTS (
          SELECT 1 FROM Ordens O
          WHERE O.Filial = H.H6_FILIAL AND O.OP = H.H6_OP
      )
    GROUP BY H.H6_FILIAL, H.H6_OP
),
OrdensNoPeriodo AS (
    SELECT O.*
    FROM Ordens O
    CROSS JOIN Parametros F
    LEFT JOIN DatasPorOP D ON D.Filial = O.Filial AND D.OP = O.OP
    WHERE (F.DataInicial IS NULL OR COALESCE(D.DataFim, D.DataInicio) >= F.DataInicial)
      AND (F.DataFinal IS NULL OR COALESCE(D.DataInicio, D.DataFim) <= F.DataFinal)
      AND (F.DataInicial IS NULL OR F.DataFinal IS NULL OR F.DataInicial <= F.DataFinal)
),
Apontamentos AS (
    SELECT H.H6_FILIAL AS Filial, H.H6_OP AS OP, H.H6_OPERAC AS Operacao,
           H.H6_OPERADO AS Operador, H.H6_RECURSO AS RecursoApontado,
           H.H6_PRODUTO AS Produto, H.H6_QTDPROD AS Quantidade,
           TRIM(H.H6_LOTECTL) AS LoteProduzido,
           TRIM(H.H6_XLOTELI) AS LoteConsumido,
           H.R_E_C_N_O_ AS Recno,
           TO_DATE(TRIM(H.H6_DATAINI) DEFAULT NULL ON CONVERSION ERROR,
                   'FXYYYYMMDD') AS DataInicio,
           TO_DATE(TRIM(H.H6_DATAFIN) DEFAULT NULL ON CONVERSION ERROR,
                   'FXYYYYMMDD') AS DataFim,
           TO_DATE(
               CASE WHEN LENGTH(TRIM(H.H6_HORAINI)) = 5
                    THEN TRIM(H.H6_HORAINI) || ':00'
                    ELSE TRIM(H.H6_HORAINI) END
               DEFAULT NULL ON CONVERSION ERROR, 'FXHH24:MI:SS'
           ) AS HoraInicio,
           TO_DATE(
               CASE WHEN LENGTH(TRIM(H.H6_HORAFIN)) = 5
                    THEN TRIM(H.H6_HORAFIN) || ':00'
                    ELSE TRIM(H.H6_HORAFIN) END
               DEFAULT NULL ON CONVERSION ERROR, 'FXHH24:MI:SS'
           ) AS HoraFim
    FROM SH6010 H
    WHERE H.D_E_L_E_T_ = ' '
      AND EXISTS (
          SELECT 1 FROM OrdensNoPeriodo O
          WHERE O.Filial = H.H6_FILIAL AND O.OP = H.H6_OP
      )
),
IntervalosApontados AS (
    SELECT A.*,
           A.DataInicio + (A.HoraInicio - TRUNC(A.HoraInicio)) AS Inicio,
           A.DataFim + (A.HoraFim - TRUNC(A.HoraFim)) AS Fim
    FROM Apontamentos A
),
ApontamentosOrdenados AS (
    SELECT A.*,
           ROW_NUMBER() OVER (
               PARTITION BY A.Filial, A.OP
               ORDER BY COALESCE(A.DataFim, A.DataInicio) DESC NULLS LAST,
                        CASE WHEN A.DataFim IS NOT NULL THEN A.HoraFim
                             ELSE A.HoraInicio END DESC NULLS LAST,
                        A.Recno DESC
           ) AS OrdemRecente,
           ROW_NUMBER() OVER (
               PARTITION BY A.Filial, A.OP
               ORDER BY A.DataInicio NULLS LAST, A.HoraInicio NULLS LAST, A.Recno
           ) AS OrdemInicio,
           ROW_NUMBER() OVER (
               PARTITION BY A.Filial, A.OP
               ORDER BY A.DataFim DESC NULLS LAST, A.HoraFim DESC NULLS LAST, A.Recno DESC
           ) AS OrdemFim
    FROM IntervalosApontados A
),
ProdutosPorFilial AS (
    SELECT RTRIM(Codigo) AS Codigo, Filial, UM, Gramatura, Largura, Comprimento,
           ROW_NUMBER() OVER (
               PARTITION BY RTRIM(Codigo), Filial ORDER BY Recno DESC
           ) AS OrdemCadastro
    FROM Produtos
),
Producao AS (
    SELECT A.Filial, A.OP,
           MAX(CASE WHEN A.OrdemInicio = 1 THEN A.DataInicio END) AS DataInicio,
           MAX(CASE WHEN A.OrdemInicio = 1 THEN A.HoraInicio END) AS HoraInicio,
           MAX(CASE WHEN A.OrdemFim = 1 THEN A.DataFim END) AS DataFim,
           MAX(CASE WHEN A.OrdemFim = 1 THEN A.HoraFim END) AS HoraFim,
           SUM(CASE WHEN A.Fim > A.Inicio
                    THEN (A.Fim - A.Inicio) * 1440 END) AS MinutosReal,
           SUM(CASE WHEN A.Fim > A.Inicio
                     AND LTRIM(TRIM(A.Operacao), '0') = '5'
                    THEN (A.Fim - A.Inicio) * 1440 END) AS MinutosSetup,
           COUNT(DISTINCT A.LoteProduzido) AS LotesProduzidos,
           COUNT(DISTINCT A.LoteConsumido) AS LotesConsumidos,
           MAX(CASE WHEN A.OrdemRecente = 1 THEN A.Operacao END) AS Operacao,
           MAX(CASE WHEN A.OrdemRecente = 1 THEN A.Operador END) AS Operador,
           MAX(CASE WHEN A.OrdemRecente = 1 THEN A.RecursoApontado END) AS RecursoApontado,
           MAX(CASE WHEN A.OrdemRecente = 1 THEN A.Produto END) AS ProdutoApontado,
           SUM(CASE CASE WHEN PF.Codigo IS NOT NULL THEN PF.UM ELSE PC.UM END
               WHEN 'KG' THEN A.Quantidade / 1000
               WHEN 'FL' THEN
                   CASE WHEN PF.Codigo IS NOT NULL
                        THEN PF.Gramatura * PF.Largura * PF.Comprimento
                        ELSE PC.Gramatura * PC.Largura * PC.Comprimento END
                   * A.Quantidade / 1000000000000
               WHEN 'TN' THEN A.Quantidade
           END) AS PesoProduzidoTN
    FROM ApontamentosOrdenados A
    JOIN OrdensNoPeriodo O ON O.Filial = A.Filial AND O.OP = A.OP
    LEFT JOIN ProdutosPorFilial PF
        ON PF.Codigo = COALESCE(RTRIM(A.Produto), RTRIM(O.Produto))
       AND PF.Filial = TRIM(A.Filial) AND PF.OrdemCadastro = 1
    LEFT JOIN ProdutosPorFilial PC
        ON PC.Codigo = COALESCE(RTRIM(A.Produto), RTRIM(O.Produto))
       AND PC.Filial IS NULL AND PC.OrdemCadastro = 1
    GROUP BY A.Filial, A.OP
),
OrdensFiltradas AS (
    SELECT O.*, PR.DataInicio, PR.HoraInicio, PR.DataFim, PR.HoraFim,
           PR.LotesProduzidos, PR.LotesConsumidos, PR.PesoProduzidoTN,
           PR.OP AS OPApontada, PR.Operacao, PR.Operador,
           PR.RecursoApontado, PR.ProdutoApontado,
           PR.MinutosReal, PR.MinutosSetup,
           (PR.DataFim - PR.DataInicio
            + (PR.HoraFim - TRUNC(PR.HoraFim))
            - (PR.HoraInicio - TRUNC(PR.HoraInicio))) * 1440 AS MinutosProducao
    FROM OrdensNoPeriodo O
    LEFT JOIN Producao PR ON PR.Filial = O.Filial AND PR.OP = O.OP
),
JanelasProducao AS (
    SELECT DISTINCT Filial, OP, RecursoApontado, RTRIM(Produto) AS Produto,
           Inicio, Fim
    FROM IntervalosApontados
    WHERE Fim > Inicio
      AND TRIM(Operador) IS NOT NULL
      AND TRIM(RecursoApontado) IS NOT NULL
),
LimitesPorMaquina AS (
    SELECT Filial, RecursoApontado,
           TO_CHAR(MIN(Inicio), 'YYYYMMDD') AS PrimeiroDia,
           TO_CHAR(MAX(Fim), 'YYYYMMDD') AS UltimoDia
    FROM JanelasProducao
    GROUP BY Filial, RecursoApontado
),
ParadasMaquina AS (
    SELECT H.H6_FILIAL AS Filial, H.H6_RECURSO AS Recurso,
           RTRIM(H.H6_PRODUTO) AS Produto,
           TO_DATE(
               TRIM(H.H6_DATAINI) || ' ' ||
               CASE WHEN LENGTH(TRIM(H.H6_HORAINI)) = 5
                    THEN TRIM(H.H6_HORAINI) || ':00'
                    ELSE TRIM(H.H6_HORAINI) END
               DEFAULT NULL ON CONVERSION ERROR, 'FXYYYYMMDD HH24:MI:SS'
           ) AS Inicio,
           TO_DATE(
               TRIM(H.H6_DATAFIN) || ' ' ||
               CASE WHEN LENGTH(TRIM(H.H6_HORAFIN)) = 5
                    THEN TRIM(H.H6_HORAFIN) || ':00'
                    ELSE TRIM(H.H6_HORAFIN) END
               DEFAULT NULL ON CONVERSION ERROR, 'FXYYYYMMDD HH24:MI:SS'
           ) AS Fim
    FROM LimitesPorMaquina L
    JOIN SH6010 H
      ON H.H6_FILIAL = L.Filial
     AND H.H6_RECURSO = L.RecursoApontado
     AND H.H6_DATAINI <= L.UltimoDia
     AND H.H6_DATAFIN >= L.PrimeiroDia
    WHERE H.D_E_L_E_T_ = ' '
      AND TRIM(H.H6_OP) IS NULL
      AND TRIM(H.H6_MOTIVO) IS NOT NULL
),
TrechosParada AS (
    SELECT DISTINCT J.Filial, J.OP,
           GREATEST(J.Inicio, P.Inicio) AS Inicio,
           LEAST(J.Fim, P.Fim) AS Fim
    FROM JanelasProducao J
    JOIN ParadasMaquina P
      ON P.Filial = J.Filial
     AND P.Recurso = J.RecursoApontado
     AND (P.Produto IS NULL OR P.Produto = J.Produto)
     AND P.Inicio < J.Fim
     AND P.Fim > J.Inicio
    WHERE P.Fim > P.Inicio
),
TrechosOrdenados AS (
    SELECT T.*,
           MAX(T.Fim) OVER (
               PARTITION BY T.Filial, T.OP
               ORDER BY T.Inicio, T.Fim
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
           ) AS FimAnterior
    FROM TrechosParada T
),
ParadasPorOP AS (
    SELECT Filial, OP,
           SUM(GREATEST(
               0, Fim - GREATEST(Inicio, NVL(FimAnterior, Inicio))
           )) * 1440 AS MinutosParada
    FROM TrechosOrdenados
    GROUP BY Filial, OP
),
Indicadores AS (
    SELECT O.*, NVL(PM.MinutosParada, 0) AS MinutosParada,
           O.MinutosReal - NVL(O.MinutosSetup, 0) - NVL(PM.MinutosParada, 0)
               AS MinutosProducaoLiquida
    FROM OrdensFiltradas O
    LEFT JOIN ParadasPorOP PM ON PM.Filial = O.Filial AND PM.OP = O.OP
),
Empenhos AS (
    SELECT D.D4_FILIAL AS Filial, D.D4_OP AS OP, RTRIM(D.D4_COD) AS Codigo,
           P.Descricao, P.UM,
           CASE P.UM
               WHEN 'KG' THEN D.D4_QTDEORI / 1000
               WHEN 'FL' THEN P.Gramatura * P.Largura * P.Comprimento
                              * D.D4_QTDEORI / 1000000000000
               WHEN 'TN' THEN D.D4_QTDEORI
           END AS PesoTN
    FROM SD4010 D
    OUTER APPLY (
        SELECT P.*
        FROM Produtos P
        WHERE P.Codigo = D.D4_COD
          AND (P.Filial = TRIM(D.D4_FILIAL) OR P.Filial IS NULL)
        ORDER BY CASE WHEN P.Filial = TRIM(D.D4_FILIAL) THEN 0 ELSE 1 END, P.Recno DESC
        FETCH FIRST 1 ROW ONLY
    ) P
    WHERE D.D_E_L_E_T_ = ' '
      AND EXISTS (
          SELECT 1 FROM OrdensNoPeriodo O
          WHERE O.Filial = D.D4_FILIAL AND O.OP = D.D4_OP
      )
),
Consumo AS (
    SELECT Filial, OP, SUM(PesoTN) AS PesoConsumidoTN
    FROM Empenhos
    GROUP BY Filial, OP
),
Tubetes AS (
    SELECT Filial, OP,
           LISTAGG(Codigo, ' | ' ON OVERFLOW TRUNCATE '...' WITH COUNT)
               WITHIN GROUP (ORDER BY Codigo, Descricao) AS Codigos,
           LISTAGG(COALESCE(Descricao, Codigo), ' | ' ON OVERFLOW TRUNCATE '...' WITH COUNT)
               WITHIN GROUP (ORDER BY Codigo, Descricao) AS Descricoes
    FROM (
        SELECT DISTINCT Filial, OP, Codigo, Descricao
        FROM Empenhos
        WHERE UM = 'PC'
    )
    GROUP BY Filial, OP
)
SELECT
    RTRIM(O.Filial) AS "FILIAL",
    RTRIM(O.OP) AS "OP",
    CASE WHEN O.DataInicio IS NULL THEN 'NÃO INICIADA'
         WHEN O.DataFim IS NULL THEN 'EM ANDAMENTO'
         ELSE 'FINALIZADA' END AS "STATUS DA OP",
    RTRIM(O.Operacao) AS "OPERAÇÃO",
    RTRIM(G.G2_DESCRI) AS "NOME DA OPERAÇÃO",
    RTRIM(O.Recurso) AS "RECURSO",
    RTRIM(R.H1_DESCRI) AS "DESCRIÇÃO DO RECURSO",
    RTRIM(O.RecursoApontado) AS "H6_RECURSO",
    RTRIM(RA.H1_DESCRI) AS "DESCRIÇÃO DO RECURSO APONTADO",
    RTRIM(O.Roteiro) AS "ROTEIRO",
    RTRIM(O.Operador) AS "OPERADOR",
    RTRIM(O.Cliente) AS "CLIENTE",
    RTRIM(C.A1_NOME) AS "NOME CLIENTE",
    RTRIM(O.ProdutoApontado) AS "PRODUTO FINAL",
    P.UM AS "UNIDADE DE MEDIDA",
    CASE WHEN P.UM = 'FL' THEN 'FOLHA' ELSE 'BOBINA' END AS "FOLHA / BOBINA",
    P.Descricao AS "DESCRIÇÃO PRODUTO",
    P.Largura AS "LARGURA DO PRODUTO FINAL",
    CASE WHEN P.UM = 'FL' THEN P.Comprimento END AS "COMPRIMENTO DO PRODUTO FINAL",
    P.Gramatura AS "GRAMATURA TOTAL",
    TO_CHAR(O.DataPrevista, 'DD/MM/YYYY') AS "DATA PREVISTA",
    CASE WHEN O.DataInicio IS NOT NULL THEN
        TO_CHAR(O.DataInicio, 'DD/MM/YYYY') ||
        CASE WHEN O.HoraInicio IS NOT NULL THEN ' ' || TO_CHAR(O.HoraInicio, 'HH24:MI') END
    END AS "DATA/HR INICIO",
    CASE WHEN O.DataFim IS NOT NULL THEN
        TO_CHAR(O.DataFim, 'DD/MM/YYYY') ||
        CASE WHEN O.HoraFim IS NOT NULL THEN ' ' || TO_CHAR(O.HoraFim, 'HH24:MI') END
    END AS "DATA/HR FIM",
    CASE WHEN O.MinutosProducaoLiquida >= 0 THEN
        CASE WHEN ROUND(O.MinutosProducaoLiquida) < 600 THEN '0' END
        || TO_CHAR(TRUNC(ROUND(O.MinutosProducaoLiquida) / 60), 'FM999999990')
        || ':' || TO_CHAR(MOD(ROUND(O.MinutosProducaoLiquida), 60), 'FM00')
    END AS "Prod. Real",
    CASE WHEN NVL(O.MinutosSetup, 0) >= 0 THEN
        CASE WHEN ROUND(NVL(O.MinutosSetup, 0)) < 600 THEN '0' END
        || TO_CHAR(TRUNC(ROUND(NVL(O.MinutosSetup, 0)) / 60), 'FM999999990')
        || ':' || TO_CHAR(MOD(ROUND(NVL(O.MinutosSetup, 0)), 60), 'FM00')
    END AS "Setup Real",
    CASE WHEN O.MinutosParada >= 0 THEN
        CASE WHEN ROUND(O.MinutosParada) < 600 THEN '0' END
        || TO_CHAR(TRUNC(ROUND(O.MinutosParada) / 60), 'FM999999990')
        || ':' || TO_CHAR(MOD(ROUND(O.MinutosParada), 60), 'FM00')
    END AS "Parada Real",
    CASE WHEN O.MinutosReal >= 0 THEN
        CASE WHEN ROUND(O.MinutosReal) < 600 THEN '0' END
        || TO_CHAR(TRUNC(ROUND(O.MinutosReal) / 60), 'FM999999990')
        || ':' || TO_CHAR(MOD(ROUND(O.MinutosReal), 60), 'FM00')
    END AS "Tempo Real",
    TO_CHAR(
        CASE WHEN O.MinutosReal > 0 THEN
            ROUND(O.PesoProduzidoTN * 60 / O.MinutosReal, 3)
        END,
        'TM9', 'NLS_NUMERIC_CHARACTERS = '',.'''
    ) AS "Real. Ton/Hora",
    TO_CHAR(
        CASE WHEN P.Largura > 0 AND P.Gramatura > 0 AND O.MinutosProducao > 0 THEN
            ROUND((O.PesoProduzidoTN * 1000)
                / ((P.Largura / 1000) * (P.Gramatura / 1000) * O.MinutosProducao), 4)
        END,
        'TM9', 'NLS_NUMERIC_CHARACTERS = '',.'''
    ) AS "VELOCIDADE M/MIN",
    TO_CHAR(
        CASE P.UM
            WHEN 'KG' THEN O.QuantidadePrevista / 1000
            WHEN 'FL' THEN P.Gramatura * P.Largura * P.Comprimento
                           * O.QuantidadePrevista / 1000000000000
            WHEN 'TN' THEN O.QuantidadePrevista
        END,
        'TM9', 'NLS_NUMERIC_CHARACTERS = '',.'''
    ) AS "QUANTIDADE PREVISTA EM TN",
    TO_CHAR(
        CASE WHEN O.OPApontada IS NULL THEN 0 ELSE O.PesoProduzidoTN END,
        'TM9', 'NLS_NUMERIC_CHARACTERS = '',.'''
    ) AS "PESO DOS LOTES PRODUZIDOS EM TN",
    NVL(O.LotesProduzidos, 0) AS "CONTAGEM DOS LOTES PRODUZIDOS",
    TO_CHAR(
        CASE WHEN E.OP IS NULL THEN 0 ELSE E.PesoConsumidoTN END,
        'TM9', 'NLS_NUMERIC_CHARACTERS = '',.'''
    ) AS "PESO DOS LOTES CONSUMIDOS EM TN",
    NVL(O.LotesConsumidos, 0) AS "CONTAGEM DOS LOTES CONSUMIDOS",
    T.Codigos AS "TUBETE",
    T.Descricoes AS "DESCRIÇÃO DO TUBETE"
FROM Indicadores O
LEFT JOIN Consumo E ON E.Filial = O.Filial AND E.OP = O.OP
LEFT JOIN Tubetes T ON T.Filial = O.Filial AND T.OP = O.OP
OUTER APPLY (
    SELECT P.*
    FROM Produtos P
    WHERE P.Codigo = CASE WHEN TRIM(O.ProdutoApontado) IS NOT NULL
                          THEN O.ProdutoApontado ELSE O.Produto END
      AND (P.Filial = TRIM(O.Filial) OR P.Filial IS NULL)
    ORDER BY CASE WHEN P.Filial = TRIM(O.Filial) THEN 0 ELSE 1 END, P.Recno DESC
    FETCH FIRST 1 ROW ONLY
) P
OUTER APPLY (
    SELECT G.G2_DESCRI
    FROM SG2010 G
    WHERE G.D_E_L_E_T_ = ' '
      AND (TRIM(G.G2_FILIAL) = TRIM(O.Filial) OR TRIM(G.G2_FILIAL) IS NULL)
      AND G.G2_PRODUTO = P.Codigo
      AND G.G2_CODIGO = O.Roteiro
      AND G.G2_OPERAC = O.Operacao
    ORDER BY CASE WHEN TRIM(G.G2_FILIAL) = TRIM(O.Filial) THEN 0 ELSE 1 END,
             G.R_E_C_N_O_ DESC
    FETCH FIRST 1 ROW ONLY
) G
OUTER APPLY (
    SELECT H1.H1_DESCRI
    FROM SH1010 H1
    WHERE H1.D_E_L_E_T_ = ' '
      AND H1.H1_CODIGO = O.Recurso
      AND TRIM(O.Recurso) IS NOT NULL
      AND (TRIM(H1.H1_FILIAL) = TRIM(O.Filial) OR TRIM(H1.H1_FILIAL) IS NULL)
    ORDER BY CASE WHEN TRIM(H1.H1_FILIAL) = TRIM(O.Filial) THEN 0 ELSE 1 END,
             H1.R_E_C_N_O_ DESC
    FETCH FIRST 1 ROW ONLY
) R
OUTER APPLY (
    SELECT H1.H1_DESCRI
    FROM SH1010 H1
    WHERE H1.D_E_L_E_T_ = ' '
      AND H1.H1_CODIGO = O.RecursoApontado
      AND TRIM(O.RecursoApontado) IS NOT NULL
      AND (TRIM(H1.H1_FILIAL) = TRIM(O.Filial) OR TRIM(H1.H1_FILIAL) IS NULL)
    ORDER BY CASE WHEN TRIM(H1.H1_FILIAL) = TRIM(O.Filial) THEN 0 ELSE 1 END,
             H1.R_E_C_N_O_ DESC
    FETCH FIRST 1 ROW ONLY
) RA
OUTER APPLY (
    SELECT C.A1_NOME
    FROM SA1010 C
    WHERE C.D_E_L_E_T_ = ' '
      AND (TRIM(C.A1_FILIAL) = TRIM(O.Filial) OR TRIM(C.A1_FILIAL) IS NULL)
      AND C.A1_COD = O.Cliente
      AND C.A1_LOJA = O.LojaCliente
      AND TRIM(O.Cliente) IS NOT NULL
    ORDER BY CASE WHEN TRIM(C.A1_FILIAL) = TRIM(O.Filial) THEN 0 ELSE 1 END,
             C.R_E_C_N_O_ DESC
    FETCH FIRST 1 ROW ONLY
) C
ORDER BY O.Filial, O.OP
"""


def extrair_op_produtivo(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    data_inicio e data_fim no formato AAAAMMDD (convertidos pra DATE no SQL).
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(
            _SQL, conn,
            params={"data_inicio": data_inicio, "data_fim": data_fim},
        )
    finally:
        conn.close()
    return df
