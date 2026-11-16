"""
Tratamento pós-extração do Relatório Consolidado Suzano - Jhon.

Como os aliases já vêm em português direto do SELECT (com aspas duplas no
Oracle), NÃO há dicionário de renomeação. O tratamento aqui só:

  1. Strip em colunas de texto (e normaliza 'nan' que o read_sql pode gerar).
  2. Limpa "PEDIDO DO CLIENTE" quando o LEFT JOIN em SC6 não achou match
     (nesse caso o CONCAT do Oracle retorna só o '-' do meio).
  3. Formata numéricos com vírgula:
       .2f para grandezas com decimais (metragem, gramatura, diâmetro, peso)
       .0f para contagens (emendas, tirada)
  4. Ordem final (idêntica à do SELECT).
"""
import pandas as pd


COLS_2F = ["METRAGEM", "GRAMATURA", "DIAMETRO", "PESO (KG)"]
COLS_0F = ["EMENDAS", "TIRADA"]

# Ordem final = mesma ordem do SELECT em extrair.py.
ORDEM_FINAL = [
    "BOBINA MÃE",
    "VOL.ID",
    "BOBINA FILHA",
    "METRAGEM",
    "GRAMATURA",
    "DIAMETRO",
    "PESO (KG)",
    "EMENDAS",
    "POSIÇÃO",
    "TIRADA",
    "LOTE TECHNOCOAT",
    "NÚMERO DA OP",
    "PEDIDO DO CLIENTE",
]


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

    # 1) Strip em colunas de texto (trata 'nan' residual).
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")

    # 2) "PEDIDO DO CLIENTE" — quando o LEFT JOIN em C6 não acha, o Oracle
    #    faz NULL || '-' || NULL = '-', que polui o CSV. Troca por vazio.
    if "PEDIDO DO CLIENTE" in df.columns:
        df["PEDIDO DO CLIENTE"] = df["PEDIDO DO CLIENTE"].where(
            df["PEDIDO DO CLIENTE"].str.strip() != "-", ""
        )

    # 3) Numéricos.
    for col in COLS_2F:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 2))
    for col in COLS_0F:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 0))

    # 4) Ordem final.
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]

    return df
