"""
Tratamento pós-extração do SD4 SUZANO.

Regras aplicadas (mesmo padrão dos outros relatórios prontos):
  1. Strip em colunas de texto.
  2. Renomear para nomes amigáveis.
  3. Data D4_DATA: AAAAMMDD -> DD/MM/AAAA.
  4. Formatar quantidades com '.4f' e vírgula.
  5. Ordem final.

Observação sobre D4_COD e D4_PRODUTO — são coisas diferentes no SD4:
  D4_COD:     código do INSUMO empenhado
  D4_PRODUTO: código do PRODUTO PAI (o item final da OP)
Renomeamos para deixar essa distinção clara.
"""
import pandas as pd


RENOMEAR = {
    "D4_FILIAL":   "FILIAL",
    "D4_COD":      "INSUMO",
    "B1_DESC":     "DESCRICAO INSUMO",
    "B1_UM":       "UNIDADE MEDIDA",
    "D4_OP":       "ORDEM DE PRODUCAO",
    "D4_PRODUTO":  "PRODUTO PAI",
    "D4_LOCAL":    "LOCAL",
    "D4_LOTECTL":  "LOTE CONTROLE",
    "D4_XLOTE":    "LOTE X",
    "D4_ROTEIRO":  "ROTEIRO",
    "D4_DATA":     "DATA EMPENHO",
    "D4_QTDEORI":  "QUANTIDADE ORIGINAL",
    "D4_QUANT":    "QUANTIDADE EMPENHADA",
    "D4_SLDEMP":   "SALDO EMPENHO",
}

COLS_QUANTIDADE = ["QUANTIDADE ORIGINAL", "QUANTIDADE EMPENHADA", "SALDO EMPENHO"]
COLS_DATA = ["DATA EMPENHO"]

ORDEM_FINAL = [
    "FILIAL",
    "ORDEM DE PRODUCAO",
    "PRODUTO PAI",
    "INSUMO",
    "DESCRICAO INSUMO",
    "UNIDADE MEDIDA",
    "LOCAL",
    "LOTE CONTROLE",
    "LOTE X",
    "ROTEIRO",
    "DATA EMPENHO",
    "QUANTIDADE ORIGINAL",
    "QUANTIDADE EMPENHADA",
    "SALDO EMPENHO",
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
