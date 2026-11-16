"""
Extração do SD3010 — Movimentações internas de estoque (SD3 + SB1 + SBM).

Filtros aplicados:
  - D3_OP <> ' '            (só linhas com Ordem de Produção preenchida)
  - D_E_L_E_T_ = ' '        (não deletadas)
  - D3_FILIAL NOT IN (...)  (filiais excluídas — ver FILIAIS_EXCLUIDAS)
  - D3_EMISSAO BETWEEN ...  (período informado pelo usuário)
"""
import pandas as pd

from app.oracle import get_oracle_connection


# Filiais que nunca devem entrar no relatório.
# Editável — para adicionar/remover, ajuste esta lista.
FILIAIS_EXCLUIDAS = [
    "0101003",
    "0101006",
]


def extrair_sd3010(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """
    Parâmetros:
        data_inicio, data_fim: strings no formato AAAAMMDD (filtro sobre D3_EMISSAO)
    """
    # Cláusula NOT IN (segura porque FILIAIS_EXCLUIDAS é whitelist estática).
    if FILIAIS_EXCLUIDAS:
        lista_filiais = ", ".join(f"'{f}'" for f in FILIAIS_EXCLUIDAS)
        filtro_filiais = f"AND D3_FILIAL NOT IN ({lista_filiais})"
    else:
        filtro_filiais = ""

    query = f"""
        SELECT
            D3_FILIAL,
            D3_COD,
            D3_SEQCALC,
            B1_DESC,
            D3_CF,
            D3_TM,
            D3_UM,
            D3_QUANT,
            D3_OP,
            D3_EMISSAO,
            D3_GRUPO,
            BM_DESC,
            D3_CUSTO1,
            D3_PARCTOT,
            D3_TIPO,
            D3_LOTECTL,
            D3_PERDA
        FROM SD3010 SD3
            INNER JOIN SB1010 SB1
                ON B1_COD = D3_COD
                AND SB1.D_E_L_E_T_ = ' '
            INNER JOIN SBM010 SBM
                ON BM_GRUPO = D3_GRUPO
                AND SBM.D_E_L_E_T_ = ' '
        WHERE D3_OP <> ' '
          AND SD3.D_E_L_E_T_ = ' '
          AND D3_EMISSAO BETWEEN :data_inicio AND :data_fim
          {filtro_filiais}
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
    for col in ["D3_FILIAL", "D3_COD", "D3_CF", "D3_TM", "D3_OP",
                "D3_GRUPO", "D3_LOTECTL", "D3_SEQCALC", "D3_TIPO"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
