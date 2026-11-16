"""
Tratamento pós-extração do SB8 SUZANO.

Regras aplicadas (mesmo padrão dos outros relatórios prontos):
  1. Strip em colunas de texto.
  2. Renomear para nomes amigáveis.
  3. Data B8_DFABRIC: AAAAMMDD -> DD/MM/AAAA.
  4. Formatar numéricos com '.4f' e vírgula (quantidades / saldos).
  5. Ordem final.
"""
import pandas as pd


RENOMEAR = {
    "B8_FILIAL":   "FILIAL",
    "B8_PRODUTO":  "PRODUTO",
    "B8_LOCAL":    "LOCAL",
    "B8_LOTECTL":  "LOTE CONTROLE",
    "B8_DOC":      "DOCUMENTO",
    "B8_DFABRIC":  "DATA FABRICACAO",
    "B8_QTDORI":   "QUANTIDADE ORIGINAL",
    "B8_SALDO":    "SALDO",
    "B8_EMPENHO":  "EMPENHO",
}

COLS_QUANTIDADE = ["QUANTIDADE ORIGINAL", "SALDO", "EMPENHO"]

ORDEM_FINAL = [
    "FILIAL",
    "PRODUTO",
    "LOCAL",
    "LOTE CONTROLE",
    "DOCUMENTO",
    "DATA FABRICACAO",
    "QUANTIDADE ORIGINAL",
    "SALDO",
    "EMPENHO",
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
    if "DATA FABRICACAO" in df.columns:
        df["DATA FABRICACAO"] = df["DATA FABRICACAO"].apply(_formatar_data)

    # 4) Numéricos.
    for col in COLS_QUANTIDADE:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 4))

    # 5) Ordem final.
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]

    return df
