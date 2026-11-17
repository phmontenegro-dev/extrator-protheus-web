"""
Extração de Paradas de Máquina.

Cruza eventos de parada (SH6 com motivo e sem OP) com eventos de produção
(SH6 com OP e operador) na mesma máquina/filial, por sobreposição temporal:
cada parada é associada à OP que estava rodando no mesmo recurso quando
ela aconteceu.

Filtro parametrizado: H6_DATAFIN da PARADA entre as datas informadas.

Notas sobre o SQL:
  - O WITH PARAMETROS da versão original foi substituído por bind variables
    :data_inicio e :data_fim (padrão seguro contra SQL injection).
  - Usa REGEXP + TO_DATE 'FXYYYYMMDDHH24MI' pra montar timestamp a partir das
    colunas separadas de data (AAAAMMDD) e hora (HH:MM) do Protheus,
    descartando valores malformados.
  - Faz LEFT JOIN em CYN pra trazer a descrição amigável do motivo da parada.
  - O INNER JOIN entre PARADAS e PRODUÇÃO exige:
      - mesma filial e mesma máquina
      - sobreposição temporal (fim da produção >= início da parada,
        início da produção <= fim da parada)
      - se a parada tem produto informado, ele precisa bater com o da OP
"""
import pandas as pd

from app.oracle import get_oracle_connection


def extrair_paradas_maquina(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Parâmetros:
        data_inicio, data_fim: strings AAAAMMDD
            (filtro aplicado em H6_DATAFIN das paradas)
    """
    query = """
        WITH BASE AS (
            SELECT
                H6.*,
                CASE
                    WHEN REGEXP_LIKE(TRIM(H6.H6_DATAINI), '^[0-9]{8}$')
                     AND REGEXP_LIKE(TRIM(H6.H6_HORAINI), '^[0-9]{2}:[0-9]{2}$')
                     AND TO_NUMBER(SUBSTR(TRIM(H6.H6_HORAINI), 1, 2)) BETWEEN 0 AND 23
                     AND TO_NUMBER(SUBSTR(TRIM(H6.H6_HORAINI), 4, 2)) BETWEEN 0 AND 59
                    THEN TO_DATE(
                        TRIM(H6.H6_DATAINI) ||
                        REPLACE(TRIM(H6.H6_HORAINI), ':', ''),
                        'FXYYYYMMDDHH24MI'
                    )
                END AS DT_INICIO,
                CASE
                    WHEN REGEXP_LIKE(TRIM(H6.H6_DATAFIN), '^[0-9]{8}$')
                     AND REGEXP_LIKE(TRIM(H6.H6_HORAFIN), '^[0-9]{2}:[0-9]{2}$')
                     AND TO_NUMBER(SUBSTR(TRIM(H6.H6_HORAFIN), 1, 2)) BETWEEN 0 AND 23
                     AND TO_NUMBER(SUBSTR(TRIM(H6.H6_HORAFIN), 4, 2)) BETWEEN 0 AND 59
                    THEN TO_DATE(
                        TRIM(H6.H6_DATAFIN) ||
                        REPLACE(TRIM(H6.H6_HORAFIN), ':', ''),
                        'FXYYYYMMDDHH24MI'
                    )
                END AS DT_FIM
            FROM SH6010 H6
            WHERE H6.D_E_L_E_T_ = ' '
        ),
        PARADAS AS (
            SELECT *
            FROM BASE
            WHERE TRIM(H6_MOTIVO) IS NOT NULL
              AND TRIM(H6_OP) IS NULL
              AND DT_INICIO IS NOT NULL
              AND DT_FIM IS NOT NULL
        ),
        PRODUCAO AS (
            SELECT *
            FROM BASE
            WHERE TRIM(H6_OP) IS NOT NULL
              AND TRIM(H6_OPERADO) IS NOT NULL
              AND DT_INICIO IS NOT NULL
              AND DT_FIM IS NOT NULL
        )
        SELECT
            P.H6_FILIAL AS FILIAL,
            P.H6_DATAINI AS DATA_PARADA,
            P.H6_RECURSO AS MAQUINA,
            PR.H6_OP AS OP,
            PR.H6_PRODUTO AS COD_PRODUTO,
            PR.H6_OPERADO AS OPERADOR,
            P.H6_MOTIVO AS COD_MOTIVO,
            C.CYN_DSSP AS DESCRICAO_PARADA,
            P.H6_HORAINI AS HORA_INICIAL_PARADA,
            P.H6_HORAFIN AS HORA_FINAL_PARADA,
            ROUND((P.DT_FIM - P.DT_INICIO) * 1440, 2) AS TEMPO_PARADA_MIN,
            P.H6_PRODUTO AS PRODUTO_PARADA,
            PR.H6_DATAINI AS DATA_INICIO_PRODUCAO,
            PR.H6_HORAINI AS HORA_INICIO_PRODUCAO,
            PR.H6_DATAFIN AS DATA_FIM_PRODUCAO,
            PR.H6_HORAFIN AS HORA_FIM_PRODUCAO,
            P.R_E_C_N_O_ AS REC_PARADA,
            PR.R_E_C_N_O_ AS REC_PRODUCAO
        FROM PARADAS P
            INNER JOIN PRODUCAO PR
                ON PR.H6_FILIAL = P.H6_FILIAL
                AND PR.H6_RECURSO = P.H6_RECURSO
                AND PR.DT_INICIO <= P.DT_FIM
                AND PR.DT_FIM >= P.DT_INICIO
                AND (
                    TRIM(P.H6_PRODUTO) IS NULL
                    OR P.H6_PRODUTO = PR.H6_PRODUTO
                )
            LEFT JOIN CYN010 C
                ON TRIM(C.CYN_CDSP) = TRIM(P.H6_MOTIVO)
                AND C.D_E_L_E_T_ = ' '
        WHERE P.H6_DATAFIN BETWEEN :data_inicio AND :data_fim
        ORDER BY
            P.H6_RECURSO,
            P.H6_DATAINI,
            P.H6_HORAINI
    """
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(
            query, conn,
            params={"data_inicio": data_inicio, "data_fim": data_fim},
        )
    finally:
        conn.close()

    # Códigos como texto (preserva zeros à esquerda).
    for col in ["FILIAL", "MAQUINA", "OP", "COD_PRODUTO",
                "OPERADOR", "COD_MOTIVO", "PRODUTO_PARADA"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
