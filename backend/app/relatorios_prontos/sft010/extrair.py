"""
Extração do SFT010 — Documentos de saída e entrada (SFT + tabelas relacionadas).

Duas particularidades deste relatório:

1. FILIAIS_EXCLUIDAS: filiais que nunca entram no relatório (editável).

2. Subqueries B9 (fotos de estoque em duas datas): as datas NÃO são fixas —
   são derivadas do período informado pelo usuário:
     - data_b9_anterior = último dia do MÊS ANTERIOR ao mês da data inicial
     - data_b9_final    = último dia do MÊS da data final
   Exemplo: período 01/01/2026 a 28/02/2026 → fotos em 31/12/2025 e 28/02/2026.

Os aliases das colunas B9 no SELECT são gerados dinamicamente no formato
B9C_AAAAMM / B9Q_AAAAMM (ex.: B9C_202512, B9Q_202602). O tratamento (tratar.py)
converte esses aliases para nomes amigáveis com base nas datas encontradas.
"""
from calendar import monthrange
from datetime import date

import pandas as pd

from app.oracle import get_oracle_connection


# Filiais que nunca devem entrar no relatório.
# Editável — para adicionar/remover, ajuste esta lista.
FILIAIS_EXCLUIDAS = [
    "0101003",
]


def _ultimo_dia_do_mes(ano: int, mes: int) -> date:
    ultimo = monthrange(ano, mes)[1]
    return date(ano, mes, ultimo)


def _datas_fotos_b9(data_inicio: date, data_fim: date) -> tuple[date, date]:
    """
    Calcula as duas datas das fotos de estoque a partir do período:
      - anterior: fim do mês anterior ao início do período
      - final:    fim do mês da data final do período
    """
    if data_inicio.month == 1:
        anterior = date(data_inicio.year - 1, 12, 31)
    else:
        anterior = _ultimo_dia_do_mes(data_inicio.year, data_inicio.month - 1)

    final = _ultimo_dia_do_mes(data_fim.year, data_fim.month)
    return anterior, final


def extrair_sft010(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Parâmetros:
        data_inicio, data_fim: strings no formato AAAAMMDD (filtro sobre FT_ENTRADA)
    """
    # Parse dos AAAAMMDD para calcular as datas das fotos B9.
    di = date(int(data_inicio[0:4]), int(data_inicio[4:6]), int(data_inicio[6:8]))
    df_ = date(int(data_fim[0:4]), int(data_fim[4:6]), int(data_fim[6:8]))
    b9_anterior, b9_final = _datas_fotos_b9(di, df_)

    b9_anterior_str = b9_anterior.strftime("%Y%m%d")   # ex.: '20251231'
    b9_final_str = b9_final.strftime("%Y%m%d")         # ex.: '20260228'
    b9_anterior_alias = b9_anterior.strftime("%Y%m")   # ex.: '202512'
    b9_final_alias = b9_final.strftime("%Y%m")         # ex.: '202602'

    # Cláusula NOT IN para as filiais excluídas (só entra se houver filiais na
    # lista). Nomes de filial são whitelisted na constante FILIAIS_EXCLUIDAS,
    # então a interpolação é segura.
    if FILIAIS_EXCLUIDAS:
        lista_filiais = ", ".join(f"'{f}'" for f in FILIAIS_EXCLUIDAS)
        filtro_filiais = f"AND SFT.FT_FILIAL NOT IN ({lista_filiais})"
    else:
        filtro_filiais = ""

    query = f"""
        SELECT
            SFT.FT_FILIAL,
            SFT.FT_TIPOMOV,
            SFT.FT_CLIEFOR,
            COALESCE(SA1.A1_NOME, SA2.A2_NOME) AS NOME_CLIEFOR,
            SFT.FT_NFISCAL,
            SFT.FT_PRODUTO,
            SB1.B1_DESC,
            SB1.B1_TIPO,
            SB1.B1_GRUPO,
            SBM.BM_DESC,
            SB1.B1_EXPRESS AS EXPRESSO,
            SB1.B1_UM,
            SFT.FT_OBSERV,
            SFT.FT_CFOP,
            SFT.FT_TES,
            SF4.F4_TEXTO,
            CASE SF4.F4_TRANFIL
                WHEN '2' THEN 'NAO'
                ELSE 'SIM'
            END AS TRANSF,
            SUM(SFT.FT_PRCUNIT) AS T_PRUNIT,
            SUM(SFT.FT_TOTAL)   AS T_TOTITEM,
            SUM(SFT.FT_QUANT)   AS T_QUANT,
            SUM(SFT.FT_VALICM)  AS ICM,
            SUM(SFT.FT_VALIPI)  AS IPI,
            SUM(SFT.FT_VALPIS)  AS PIS,
            SUM(SFT.FT_VALCOF)  AS COFINS,
            SUM(CASE WHEN SFT.FT_TIPOMOV = 'E' THEN SD1.D1_CUSTO  ELSE 0 END) AS CUSTO_ENTRADA,
            SUM(CASE WHEN SFT.FT_TIPOMOV = 'S' THEN SD2.D2_CUSTO1 ELSE 0 END) AS CUSTO_SAIDA,
            (SELECT B9_CM1  FROM SB9010
              WHERE B9_FILIAL = SFT.FT_FILIAL
                AND B9_COD    = SFT.FT_PRODUTO
                AND B9_DATA   = :b9_anterior
                AND D_E_L_E_T_ = ' '
                AND ROWNUM = 1) AS B9C_{b9_anterior_alias},
            (SELECT B9_QINI FROM SB9010
              WHERE B9_FILIAL = SFT.FT_FILIAL
                AND B9_COD    = SFT.FT_PRODUTO
                AND B9_DATA   = :b9_anterior
                AND D_E_L_E_T_ = ' '
                AND ROWNUM = 1) AS B9Q_{b9_anterior_alias},
            (SELECT B9_CM1  FROM SB9010
              WHERE B9_FILIAL = SFT.FT_FILIAL
                AND B9_COD    = SFT.FT_PRODUTO
                AND B9_DATA   = :b9_final
                AND D_E_L_E_T_ = ' '
                AND ROWNUM = 1) AS B9C_{b9_final_alias},
            (SELECT B9_QINI FROM SB9010
              WHERE B9_FILIAL = SFT.FT_FILIAL
                AND B9_COD    = SFT.FT_PRODUTO
                AND B9_DATA   = :b9_final
                AND D_E_L_E_T_ = ' '
                AND ROWNUM = 1) AS B9Q_{b9_final_alias}
        FROM SFT010 SFT
            INNER JOIN SB1010 SB1 ON SB1.B1_COD    = SFT.FT_PRODUTO AND SB1.D_E_L_E_T_ = ' '
            INNER JOIN SBM010 SBM ON SBM.BM_GRUPO  = SB1.B1_GRUPO   AND SBM.D_E_L_E_T_ = ' '
            LEFT  JOIN SA1010 SA1 ON SA1.A1_COD    = SFT.FT_CLIEFOR AND SA1.A1_LOJA = SFT.FT_LOJA AND SA1.D_E_L_E_T_ = ' '
            LEFT  JOIN SA2010 SA2 ON SA2.A2_COD    = SFT.FT_CLIEFOR AND SA2.A2_LOJA = SFT.FT_LOJA AND SA2.D_E_L_E_T_ = ' '
            LEFT  JOIN SF4010 SF4 ON SF4.F4_CODIGO = SFT.FT_TES     AND SF4.D_E_L_E_T_ = ' '
            LEFT  JOIN SD1010 SD1 ON SD1.D1_FILIAL  = SFT.FT_FILIAL
                                 AND SD1.D1_DOC     = SFT.FT_NFISCAL
                                 AND SD1.D1_SERIE   = SFT.FT_SERIE
                                 AND SD1.D1_COD     = SFT.FT_PRODUTO
                                 AND SD1.D1_FORNECE = SFT.FT_CLIEFOR
                                 AND SD1.D1_LOJA    = SFT.FT_LOJA
                                 AND SFT.FT_TIPOMOV = 'E'
                                 AND SD1.D_E_L_E_T_ = ' '
            LEFT  JOIN SD2010 SD2 ON SD2.D2_FILIAL  = SFT.FT_FILIAL
                                 AND SD2.D2_DOC     = SFT.FT_NFISCAL
                                 AND SD2.D2_SERIE   = SFT.FT_SERIE
                                 AND SD2.D2_COD     = SFT.FT_PRODUTO
                                 AND SD2.D2_CLIENTE = SFT.FT_CLIEFOR
                                 AND SD2.D2_LOJA    = SFT.FT_LOJA
                                 AND SFT.FT_TIPOMOV = 'S'
                                 AND SD2.D_E_L_E_T_ = ' '
        WHERE SFT.FT_ENTRADA BETWEEN :data_inicio AND :data_fim
          AND SFT.D_E_L_E_T_ = ' '
          {filtro_filiais}
        GROUP BY
            SFT.FT_FILIAL,
            SFT.FT_TIPOMOV,
            SFT.FT_CLIEFOR,
            SA1.A1_NOME,
            SA2.A2_NOME,
            SFT.FT_NFISCAL,
            SFT.FT_PRODUTO,
            SB1.B1_DESC,
            SB1.B1_TIPO,
            SB1.B1_GRUPO,
            SBM.BM_DESC,
            SB1.B1_EXPRESS,
            SB1.B1_UM,
            SFT.FT_OBSERV,
            SFT.FT_CFOP,
            SFT.FT_TES,
            SF4.F4_TEXTO,
            SF4.F4_TRANFIL
    """

    conn = get_oracle_connection()
    try:
        df = pd.read_sql(
            query,
            conn,
            params={
                "data_inicio": data_inicio,
                "data_fim": data_fim,
                "b9_anterior": b9_anterior_str,
                "b9_final": b9_final_str,
            },
        )
    finally:
        conn.close()

    # Mantém códigos como texto (preserva zeros à esquerda).
    for col in ["FT_FILIAL", "FT_CLIEFOR", "FT_NFISCAL",
                "FT_PRODUTO", "B1_GRUPO", "FT_CFOP", "FT_TES"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
