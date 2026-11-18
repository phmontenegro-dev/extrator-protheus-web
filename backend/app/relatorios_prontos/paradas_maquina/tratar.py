"""
Tratamento pós-extração de Paradas de Máquina.

Regras:
  1. Strip em colunas texto.
  2. Renomear pra nomes com acentos e espaços (aliases amigáveis).
  3. Formatar datas AAAAMMDD → DD/MM/AAAA nas 3 colunas de data.
  4. Formatar o tempo da parada (minutos) com vírgula decimal.
  5. Colunas técnicas REC_PARADA / REC_PRODUCAO ficam por último (úteis
     para rastrear o registro de origem no Protheus, mas não interessam
     no dia a dia).
  6. Ordem final.
"""
import pandas as pd


RENOMEAR = {
    "FILIAL":               "FILIAL",
    "DATA_PARADA":          "DATA DA PARADA",
    "COD_MAQUINA":          "CÓDIGO DA MÁQUINA",
    "DESCRICAO_MAQUINA":    "DESCRIÇÃO DA MÁQUINA",
    "OP":                   "ORDEM DE PRODUÇÃO",
    "COD_PRODUTO":          "CÓDIGO DO PRODUTO",
    "OPERADOR":             "OPERADOR",
    "COD_MOTIVO":           "CÓDIGO DO MOTIVO",
    "DESCRICAO_PARADA":     "MOTIVO DA PARADA",
    "HORA_INICIAL_PARADA":  "HORA INICIAL DA PARADA",
    "HORA_FINAL_PARADA":    "HORA FINAL DA PARADA",
    "TEMPO_PARADA_MIN":     "TEMPO DE PARADA (MIN)",
    "PRODUTO_PARADA":       "PRODUTO (PARADA)",
    "DATA_INICIO_PRODUCAO": "DATA INÍCIO DA PRODUÇÃO",
    "HORA_INICIO_PRODUCAO": "HORA INÍCIO DA PRODUÇÃO",
    "DATA_FIM_PRODUCAO":    "DATA FIM DA PRODUÇÃO",
    "HORA_FIM_PRODUCAO":    "HORA FIM DA PRODUÇÃO",
    "REC_PARADA":           "REC PARADA",
    "REC_PRODUCAO":         "REC PRODUÇÃO",
}

COLS_DATA = [
    "DATA DA PARADA",
    "DATA INÍCIO DA PRODUÇÃO",
    "DATA FIM DA PRODUÇÃO",
]

COLS_TEMPO = ["TEMPO DE PARADA (MIN)"]

ORDEM_FINAL = [
    "FILIAL",
    "CÓDIGO DA MÁQUINA",
    "DESCRIÇÃO DA MÁQUINA",
    "DATA DA PARADA",
    "HORA INICIAL DA PARADA",
    "HORA FINAL DA PARADA",
    "TEMPO DE PARADA (MIN)",
    "CÓDIGO DO MOTIVO",
    "MOTIVO DA PARADA",
    "PRODUTO (PARADA)",
    "ORDEM DE PRODUÇÃO",
    "CÓDIGO DO PRODUTO",
    "OPERADOR",
    "DATA INÍCIO DA PRODUÇÃO",
    "HORA INÍCIO DA PRODUÇÃO",
    "DATA FIM DA PRODUÇÃO",
    "HORA FIM DA PRODUÇÃO",
    # Técnicas — ficam no fim pra quem quiser rastrear registro no Protheus.
    "REC PARADA",
    "REC PRODUÇÃO",
]


def _formatar_data(valor) -> str:
    """AAAAMMDD → DD/MM/AAAA"""
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

    # 4) Tempo em minutos com 2 casas decimais e vírgula.
    for col in COLS_TEMPO:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 2))

    # 5) Ordem final.
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]

    # Dedup opcional: mesmo join por sobreposição temporal pode produzir
    # linhas idênticas se uma parada "casa" com várias produções que se
    # sobrepõem exatamente. Remove só as 100% iguais, igual ao CT2010.
    df = df.drop_duplicates().reset_index(drop=True)

    return df
