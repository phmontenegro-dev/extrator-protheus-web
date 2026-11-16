"""
Tratamento pós-extração do SD2 SUZANO.

Regras aplicadas (mesmo padrão dos outros relatórios prontos):
  1. Strip em colunas de texto.
  2. Renomear para nomes amigáveis.
  3. Data D2_EMISSAO: AAAAMMDD -> DD/MM/AAAA.
  4. Formatar QUANTIDADE com '.4f' e vírgula.
  5. Ordem final.
"""
import pandas as pd


RENOMEAR = {
    "D2_FILIAL":   "FILIAL",
    "D2_COD":      "PRODUTO",
    "D2_UM":       "UNIDADE MEDIDA",
    "D2_TES":      "TES",
    "D2_CF":       "CFOP",
    "D2_CLIENTE":  "CLIENTE",
    "D2_LOCAL":    "LOCAL",
    "D2_DOC":      "DOCUMENTO",
    "D2_LOTECTL":  "LOTE CONTROLE",
    "D2_TP":       "TIPO",
    "D2_EMISSAO":  "DATA EMISSAO",
    "D2_QUANT":    "QUANTIDADE",
}

COLS_QUANTIDADE = ["QUANTIDADE"]
COLS_DATA = ["DATA EMISSAO"]

ORDEM_FINAL = [
    "FILIAL",
    "PRODUTO",
    "UNIDADE MEDIDA",
    "CLIENTE",
    "LOCAL",
    "DOCUMENTO",
    "LOTE CONTROLE",
    "TES",
    "CFOP",
    "TIPO",
    "DATA EMISSAO",
    "QUANTIDADE",
]


def _formatar_data(valor) -> str:
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

    # 1) Strip em colunas de texto.
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")

    # 2) Renomear.
    df = df.rename(columns=RENOMEAR)

    # 3) Data.
    for col in COLS_DATA:
        if col in df.columns:
            df[col] = df[col].apply(_formatar_data)

    # 4) Numéricos.
    for col in COLS_QUANTIDADE:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 4))

    # 5) Ordem final.
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]

    return df
