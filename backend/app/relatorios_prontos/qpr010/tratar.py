import pandas as pd


# Se True, mantém apenas linhas onde H6_LOTECTL == QPR_LOTE (lotes consistentes)
VERIFICAR_LOTE = True

# Se True, mantém apenas a medição mais antiga para cada LOTE FINAL + ENSAIO
DEDUP_LOTE_ENSAIO = True

COLUNAS_REMOVER = [
    "DATA/HORA FIM OP",
    "H6_XLOTECTL",
    "QPR_CHAVE",
    "QPR_ENSR",
    "QPS_INDMED",
    # QPR_LOTE e QPR_ENSAIO NÃO entram aqui: são necessários para
    # a verificação de lote e a deduplicação. São descartados no fim pela ORDEM_FINAL.
]

# Nome final de cada coluna (rótulo mais amigável)
RENOMEAR = {
    "QPR_FILIAL": "FILIAL",
    "QPR_DTENTR": "DATA DE ENTRADA",
    "H6_XLOTELI": "LOTE DE ENTRADA",
    "H6_LOTECTL": "LOTE FINAL",          # <-- era "QPR_LOTE": "LOTE FINAL"
    "H6_XNUMBOB": "BOBINA FILHA",
    "QPR_OP": "ORDEM DE PRODUÇÃO",
    "QPR_PRODUT": "PRODUTO",
    "B1_DESC": "DESCRIÇÃO DO PRODUTO",
    "QAA_NOME": "ENSAIADOR",
    "QP1_DESCPO": "ENSAIO",
    "QP7_LIE": "MINIMO",
    "QP7_LSE": "MAXIMO",
    "QPS_MEDICA": "RESULTADO",
    "QPQ_MEDICA": "RESULTADO TEXTO",
    "QPL_JUSTLA": "JUSTIFICATIVA LAUDO",
}
# Ordem final das colunas no CSV (já com os nomes renomeados)
ORDEM_FINAL = [
    "FILIAL",
    "DATA DE ENTRADA",
    "DATA/HORA MEDICAO",
    "LOTE DE ENTRADA",
    "LOTE FINAL",
    "BOBINA FILHA",
    "ORDEM DE PRODUÇÃO",
    "PRODUTO",
    "DESCRIÇÃO DO PRODUTO",
    "ENSAIADOR",
    "ENSAIO",
    "MINIMO",
    "MAXIMO",
    "RESULTADO",
    "RESULTADO TEXTO",
    "JUSTIFICATIVA LAUDO",
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


def _chave_temporal(valor) -> str:
    """Converte 'DD/MM/AAAA HH:MM' em 'AAAAMMDDHHMM' para ordenação cronológica."""
    v = str(valor).strip()
    try:
        data_parte, hora_parte = v.split(" ")
        dd, mm, aaaa = data_parte.split("/")
        hh, mi = hora_parte.split(":")
        return f"{aaaa}{mm}{dd}{hh}{mi}"
    except Exception:
        return "999999999999"  # linhas sem data/hora válida vão para o fim


def tratar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()

    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")

    # Consolida data + hora
    df = _consolidar_data_hora(df, "QPR_DTMEDI", "QPR_HRMEDI", "DATA/HORA MEDICAO")
    df = _consolidar_data_hora(df, "H6_DATAFIN", "H6_HORAFIN", "DATA/HORA FIM OP")

    # Data de entrada (sem hora)
    if "QPR_DTENTR" in df.columns:
        df["QPR_DTENTR"] = df["QPR_DTENTR"].apply(_formatar_data)

    # Renomeia e mantém apenas as 16 colunas finais (na ordem definida)
    df = df.rename(columns=RENOMEAR)
    df = df[[c for c in ORDEM_FINAL if c in df.columns]]

    # Remove duplicatas considerando apenas as 16 colunas finais
    df = df.drop_duplicates().reset_index(drop=True)

    return df
