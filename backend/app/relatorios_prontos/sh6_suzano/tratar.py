"""
Tratamento pós-extração do SH6 SUZANO.

Regras aplicadas:
  1. Strip em colunas de texto.
  2. Consolidar data + hora em uma coluna só (padrão QPR010):
       H6_DATAINI + H6_HORAINI -> "DATA/HORA INICIO"
       H6_DATAFIN + H6_HORAFIN -> "DATA/HORA FIM"
  3. Formatar datas puras (H6_DTAPONT, H6_DTPROD): AAAAMMDD -> DD/MM/AAAA.
  4. Renomear as demais colunas para nomes amigáveis.
  5. Formatar numéricos com vírgula:
       .4f para quantidades (produção, perda)
       .2f para diâmetro
  6. Ordem final.
"""
import pandas as pd


RENOMEAR = {
    "H6_FILIAL":   "FILIAL",
    "H6_OP":       "ORDEM DE PRODUCAO",
    "H6_PRODUTO":  "PRODUTO",
    "B1_DESC":     "DESCRICAO PRODUTO",
    "B1_UM":       "UNIDADE MEDIDA",
    "H6_RECURSO":  "RECURSO",
    "H6_LOCAL":    "LOCAL",
    "H6_LOTECTL":  "LOTE CONTROLE",
    "H6_XLOTELI":  "LOTE ENTRADA",
    "H6_XNUMBOB":  "NUMERO BOBINA",
    "H6_XDIAM":    "DIAMETRO",
    "H6_DTAPONT":  "DATA APONTAMENTO",
    "H6_DTPROD":   "DATA PRODUCAO",
    "H6_QTDPROD":  "QUANTIDADE PRODUZIDA",
    "H6_QTDPERD":  "QUANTIDADE PERDIDA",
}

COLS_QUANTIDADE = ["QUANTIDADE PRODUZIDA", "QUANTIDADE PERDIDA"]
COLS_DIAMETRO = ["DIAMETRO"]
COLS_DATA = ["DATA APONTAMENTO", "DATA PRODUCAO"]

ORDEM_FINAL = [
    "FILIAL",
    "ORDEM DE PRODUCAO",
    "PRODUTO",
    "DESCRICAO PRODUTO",
    "UNIDADE MEDIDA",
    "RECURSO",
    "LOCAL",
    "LOTE CONTROLE",
    "LOTE ENTRADA",
    "NUMERO BOBINA",
    "DIAMETRO",
    "DATA/HORA INICIO",
    "DATA/HORA FIM",
    "DATA APONTAMENTO",
    "DATA PRODUCAO",
    "QUANTIDADE PRODUZIDA",
    "QUANTIDADE PERDIDA",
]


def _formatar_data(valor) -> str:
    """AAAAMMDD -> DD/MM/AAAA"""
    if not isinstance(valor, str):
        return valor
    v = valor.strip()
    if len(v) == 8 and v.isdigit():
        return f"{v[6:8]}/{v[4:6]}/{v[0:4]}"
    return v


def _formatar_hora(valor) -> str:
    """HHMM ou HHMMSS -> HH:MM"""
    if not isinstance(valor, str):
        return ""
    v = valor.strip().replace(":", "")
    if len(v) >= 4 and v.isdigit():
        return f"{v[0:2]}:{v[2:4]}"
    return valor.strip()


def _consolidar_data_hora(df: pd.DataFrame, col_data: str, col_hora: str,
                          nome_final: str) -> pd.DataFrame:
    """Junta data + hora numa coluna só e remove as originais."""
    if col_data not in df.columns:
        return df
    datas = df[col_data].apply(_formatar_data)
    if col_hora in df.columns:
        horas = df[col_hora].apply(_formatar_hora)
        df[nome_final] = (datas.fillna("") + " " + horas.fillna("")).str.strip()
        df = df.drop(columns=[col_hora])
    else:
        df[nome_final] = datas
    df = df.drop(columns=[col_data])
    return df


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

    # 2) Consolidar data + hora (antes de renomear).
    df = _consolidar_data_hora(df, "H6_DATAINI", "H6_HORAINI", "DATA/HORA INICIO")
    df = _consolidar_data_hora(df, "H6_DATAFIN", "H6_HORAFIN", "DATA/HORA FIM")

    # 3) Renomear demais colunas.
    df = df.rename(columns=RENOMEAR)

    # 4) Formatar datas puras (as que sobraram sem hora).
    for col in COLS_DATA:
        if col in df.columns:
            df[col] = df[col].apply(_formatar_data)

    # 5) Numéricos.
    for col in COLS_QUANTIDADE:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 4))
    for col in COLS_DIAMETRO:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 2))

    # 6) Ordem final.
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]

    return df
