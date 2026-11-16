"""
Tratamento pós-extração do SD3010.

Regras aplicadas:
  1. Strip em todas as colunas de texto.
  2. Renomear D3_* / B1_* / BM_* para nomes amigáveis (padrão QPR010/SFT010).
  3. Formatar DATA EMISSAO: AAAAMMDD -> DD/MM/AAAA.
  4. Formatar numéricos trocando '.' por ',':
       - .2f para valores monetários (CUSTO, PARCELA TOTAL)
       - .4f para quantidades (QUANTIDADE, PERDA)
  5. Aplicar a ordem final de colunas (ORDEM_FINAL).
"""
import pandas as pd


RENOMEAR = {
    "D3_FILIAL":   "FILIAL",
    "D3_COD":      "PRODUTO",
    "B1_DESC":     "DESCRICAO PRODUTO",
    "D3_GRUPO":    "GRUPO",
    "BM_DESC":     "DESCRICAO GRUPO",
    "D3_UM":       "UNIDADE MEDIDA",
    "D3_TIPO":     "TIPO",
    "D3_TM":       "TIPO MOVIMENTO",
    "D3_CF":       "CFOP",
    "D3_EMISSAO":  "DATA EMISSAO",
    "D3_OP":       "ORDEM DE PRODUCAO",
    "D3_LOTECTL":  "LOTE CONTROLE",
    "D3_SEQCALC":  "SEQUENCIA CALCULO",
    "D3_QUANT":    "QUANTIDADE",
    "D3_CUSTO1":   "CUSTO",
    "D3_PARCTOT":  "PARCELA TOTAL",
    "D3_PERDA":    "PERDA",
}

COLS_MONETARIAS = ["CUSTO", "PARCELA TOTAL"]
COLS_QUANTIDADE = ["QUANTIDADE", "PERDA"]

ORDEM_FINAL = [
    "FILIAL",
    "PRODUTO",
    "DESCRICAO PRODUTO",
    "GRUPO",
    "DESCRICAO GRUPO",
    "UNIDADE MEDIDA",
    "TIPO",
    "TIPO MOVIMENTO",
    "CFOP",
    "DATA EMISSAO",
    "ORDEM DE PRODUCAO",
    "LOTE CONTROLE",
    "SEQUENCIA CALCULO",
    "QUANTIDADE",
    "CUSTO",
    "PARCELA TOTAL",
    "PERDA",
]


def _formatar_data(valor) -> str:
    """AAAAMMDD -> DD/MM/AAAA"""
    if not isinstance(valor, str):
        return valor
    v = valor.strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[6:8]}/{v[4:6]}/{v[0:4]}"
    return v


def _formatar_numero(x, casas: int) -> str:
    if pd.isna(x):
        return ""
    try:
        return f"{float(x):.{casas}f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(x)


def tratar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()

    # 1) Strip em colunas texto.
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")

    # 2) Renomear.
    df = df.rename(columns=RENOMEAR)

    # 3) Data.
    if "DATA EMISSAO" in df.columns:
        df["DATA EMISSAO"] = df["DATA EMISSAO"].apply(_formatar_data)

    # 4) Formatação numérica.
    for col in COLS_MONETARIAS:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 2))

    for col in COLS_QUANTIDADE:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 4))

    # 5) Ordem final.
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]

    return df
