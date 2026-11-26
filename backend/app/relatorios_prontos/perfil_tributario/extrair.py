"""
Extração — Perfil Tributário por Produto.

Lista todos os produtos ativos (SB1010 não deletados e não bloqueados:
B1_MSBLQL <> '1'), trazendo o perfil tributário vinculado via F24010 e
a descrição do perfil via F20010.

SB1 ↔ F24010 (vínculo produto → perfil, filtrado por não deletados)
F24010 ↔ F20010 (cadastro do perfil: código + tipo + filial)

LEFT JOIN em F24 e F20 pra não perder produtos que ainda não têm perfil
atribuído — eles aparecem com COD_PERFIL/DESCRICAO_PERFIL vazios.

ORDER BY B1_COD mantido do SQL fonte pra facilitar conferência visual.
"""
import pandas as pd

from app.oracle import get_oracle_connection


_SQL = """
SELECT
    B1.B1_COD      AS COD_PRODUTO,
    B1.B1_DESC     AS DESCRICAO_PRODUTO,
    B1.B1_GRTRIB   AS GRUPO_TRIBUTARIO,
    F24.F24_CODIGO AS COD_PERFIL,
    F20.F20_DESC   AS DESCRICAO_PERFIL
FROM SB1010 B1
LEFT JOIN F24010 F24
    ON F24.F24_CDPROD = B1.B1_COD
   AND F24.D_E_L_E_T_ = ' '
LEFT JOIN F20010 F20
    ON F20.F20_CODIGO = F24.F24_CODIGO
   AND F20.F20_TIPO   = F24.F24_TIPOPF
   AND F20.F20_FILIAL = F24.F24_FILIAL
   AND F20.D_E_L_E_T_ = ' '
WHERE B1.D_E_L_E_T_ = ' '
  AND B1.B1_MSBLQL <> '1'
ORDER BY B1.B1_COD
"""


def extrair_perfil_tributario() -> pd.DataFrame:
    conn = get_oracle_connection()
    try:
        df = pd.read_sql(_SQL, conn)
    finally:
        conn.close()
    return df
