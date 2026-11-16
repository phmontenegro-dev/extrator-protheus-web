"""
Tratamento pós-extração do SD1 SUZANO.

Regras aplicadas (mesmo padrão dos outros relatórios prontos):
  1. Strip em colunas de texto.
  2. Renomear para nomes amigáveis.
  3. Datas D1_EMISSAO e D1_DTDIGIT: AAAAMMDD -> DD/MM/AAAA.
  4. Formatar QUANTIDADE com '.4f' e vírgula.
  5. Ordem final.
"""
import pandas as pd


RENOMEAR = {
    "D1_FILIAL":   "FILIAL",
    "D1_COD":      "PRODUTO",
    "D1_XDESCPR":  "DESCRICAO PRODUTO",
    "D1_UM":       "UNIDADE MEDIDA",
    "D1_LOTECTL":  "LOTE CONTROLE",
    "D1_DOC":      "DOCUMENTO",
    "D1_EMISSAO":  "DATA EMISSAO",
    "D1_DTDIGIT":  "DATA DIGITACAO",
    "D1_QUANT":    "QUANTIDADE",
}

COLS_QUANTIDADE = ["QUANTIDADE"]
COLS_DATA = ["DATA EMISSAO", "DATA DIGITACAO"]

ORDEM_FINAL = [
    "FILIAL",
    "PRODUTO",
    "DESCRICAO PRODUTO",
    "UNIDADE MEDIDA",
    "LOTE CONTROLE",
    "DOCUMENTO",
    "DATA EMISSAO",
    "DATA DIGITACAO",
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

    # 3) Datas.
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
