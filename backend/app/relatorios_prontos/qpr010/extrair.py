import pandas as pd

from app.oracle import get_oracle_connection


def extrair_qpr010(filial: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Extrai as medições de qualidade (QPR010) e tabelas relacionadas.

    Parâmetros:
        filial: código da filial (ex: "0101001")
        data_inicio, data_fim: período no formato AAAAMMDD (filtro sobre QPR_DTMEDI)
    """
    query = """
        SELECT
            QPR.*,
            QPS.QPS_MEDICA,
            QPS.QPS_INDMED,
            QPQ.QPQ_MEDICA,
            QPL.QPL_JUSTLA,
            SH6.H6_DATAFIN,
            SH6.H6_HORAFIN,
            SH6.H6_XLOTELI,
            SH6.H6_LOTECTL,
            SH6.H6_XNUMBOB,
            B1.B1_DESC,
            QP1.QP1_DESCPO,
            QP7.QP7_LIE,
            QP7.QP7_LSE,
            QAA.QAA_NOME
        FROM QPR010 QPR
            LEFT JOIN QPS010 QPS
                ON  QPS.QPS_FILIAL = QPR.QPR_FILIAL
                AND TRIM(QPS.QPS_CODMED) = TRIM(QPR.QPR_CHAVE)
                AND QPS.D_E_L_E_T_ = ' '
            LEFT JOIN QPQ010 QPQ
                ON  QPQ.QPQ_FILIAL = QPR.QPR_FILIAL
                AND TRIM(QPQ.QPQ_CODMED) = TRIM(QPR.QPR_CHAVE)
                AND QPQ.D_E_L_E_T_ = ' '
            LEFT JOIN QPL010 QPL
                ON  QPL.QPL_FILIAL = QPR.QPR_FILIAL
                AND TRIM(QPL.QPL_LOTE) = TRIM(QPR.QPR_LOTE)
                AND QPL.D_E_L_E_T_ = ' '
            LEFT JOIN SH6010 SH6
                ON  SH6.H6_FILIAL = QPR.QPR_FILIAL
                AND TRIM(SH6.H6_LOTECTL) = TRIM(QPR.QPR_LOTE)
                AND SH6.D_E_L_E_T_ = ' '
            LEFT JOIN SB1010 B1
                ON  TRIM(B1.B1_COD) = TRIM(QPR.QPR_PRODUT)
                AND B1.D_E_L_E_T_ = ' '
            LEFT JOIN QP1010 QP1
                ON  TRIM(QP1.QP1_ENSAIO) = TRIM(QPR.QPR_ENSAIO)
                AND QP1.D_E_L_E_T_ = ' '
            LEFT JOIN QP7010 QP7
                ON  TRIM(QP7.QP7_PRODUT) = TRIM(QPR.QPR_PRODUT)
                AND TRIM(QP7.QP7_ENSAIO) = TRIM(QPR.QPR_ENSAIO)
                AND QP7.D_E_L_E_T_ = ' '
            LEFT JOIN QAA010 QAA
                ON  TRIM(QAA.QAA_MAT) = TRIM(QPR.QPR_ENSR)
                AND QAA.D_E_L_E_T_ = ' '
        WHERE QPR.QPR_FILIAL = :filial
            AND QPR.QPR_DTMEDI BETWEEN :data_inicio AND :data_fim
            AND QPR.D_E_L_E_T_ = ' '
    """

    conn = get_oracle_connection()
    try:
        df = pd.read_sql(query, conn, params={
            "filial": filial,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        })
    finally:
        conn.close()

    # Mantém códigos como texto (preserva zeros à esquerda)
    for col in ["QPR_FILIAL", "QPR_LOTE", "QPR_OP", "QPR_PRODUT", "QPR_CHAVE"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
