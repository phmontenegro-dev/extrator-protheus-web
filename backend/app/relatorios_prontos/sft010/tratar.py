"""
Tratamento pós-extração do SFT010.

Regras aplicadas:
  1. Strip em todas as colunas de texto.
  2. Renomear FT_* / B1_* / etc. para nomes amigáveis (padrão QPR010).
  3. Traduzir FT_TIPOMOV: 'E' -> 'ENTRADA', 'S' -> 'SAIDA'.
  4. Formatar valores numéricos trocando '.' por ',' (padrão CT2010):
       - .2f para valores monetários (totais, impostos, custos)
       - .4f para quantidade e custo médio (preserva precisão)
  5. Renomear as duas colunas dinâmicas B9C_AAAAMM / B9Q_AAAAMM para
     'CUSTO MEDIO MM/AAAA' e 'QTD INICIAL MM/AAAA'.
  6. Aplicar a ordem final de colunas (ORDEM_FINAL).
"""
import re

import pandas as pd


# Colunas com nome fixo (não dependem do período extraído).
RENOMEAR_FIXAS = {
    "FT_FILIAL":     "FILIAL",
    "FT_TIPOMOV":    "TIPO MOV",
    "FT_CLIEFOR":    "CODIGO CLIENTE/FORNECEDOR",
    "NOME_CLIEFOR":  "NOME CLIENTE/FORNECEDOR",
    "FT_NFISCAL":    "NOTA FISCAL",
    "FT_PRODUTO":    "PRODUTO",
    "B1_DESC":       "DESCRICAO PRODUTO",
    "B1_TIPO":       "TIPO PRODUTO",
    "B1_GRUPO":      "GRUPO",
    "BM_DESC":       "DESCRICAO GRUPO",
    "EXPRESSO":      "EXPRESSO",
    "B1_UM":         "UNIDADE MEDIDA",
    "FT_OBSERV":     "OBSERVACAO",
    "FT_CFOP":       "CFOP",
    "FT_TES":        "TES",
    "F4_TEXTO":      "DESCRICAO TES",
    "TRANSF":        "TRANSFERENCIA",
    "T_QUANT":       "QUANTIDADE",
    "T_PRUNIT":      "PRECO UNITARIO",
    "T_TOTITEM":     "VALOR TOTAL ITEM",
    "ICM":           "ICMS",
    "IPI":           "IPI",
    "PIS":           "PIS",
    "COFINS":        "COFINS",
    "CUSTO_ENTRADA": "CUSTO ENTRADA",
    "CUSTO_SAIDA":   "CUSTO SAIDA",
}

MAPA_TIPOMOV = {"E": "ENTRADA", "S": "SAIDA"}

# Colunas que recebem formatação monetária .2f
COLS_MONETARIAS = [
    "PRECO UNITARIO", "VALOR TOTAL ITEM",
    "ICMS", "IPI", "PIS", "COFINS",
    "CUSTO ENTRADA", "CUSTO SAIDA",
]

# Colunas que recebem formatação .4f (quantidade, custo médio unitário).
# Nomes de "CUSTO MEDIO ..." e "QTD INICIAL ..." (das colunas B9) são
# detectados dinamicamente e adicionados a essa lista.
COLS_QUANTIDADE_BASE = ["QUANTIDADE"]

# Ordem final das colunas. As duas colunas de estoque B9 (custo médio + qtd)
# são inseridas no fim, na ordem em que aparecem no DataFrame.
ORDEM_FINAL_FIXA = [
    "FILIAL",
    "TIPO MOV",
    "CODIGO CLIENTE/FORNECEDOR",
    "NOME CLIENTE/FORNECEDOR",
    "NOTA FISCAL",
    "PRODUTO",
    "DESCRICAO PRODUTO",
    "TIPO PRODUTO",
    "GRUPO",
    "DESCRICAO GRUPO",
    "EXPRESSO",
    "UNIDADE MEDIDA",
    "OBSERVACAO",
    "CFOP",
    "TES",
    "DESCRICAO TES",
    "TRANSFERENCIA",
    "QUANTIDADE",
    "PRECO UNITARIO",
    "VALOR TOTAL ITEM",
    "ICMS",
    "IPI",
    "PIS",
    "COFINS",
    "CUSTO ENTRADA",
    "CUSTO SAIDA",
]

# Regex para detectar as colunas B9 vindas do banco (aliases dinâmicos).
_REGEX_B9 = re.compile(r"^B9(?P<tipo>[CQ])_(?P<ano>\d{4})(?P<mes>\d{2})$")


def _renomear_b9(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """
    Renomeia colunas B9C_AAAAMM / B9Q_AAAAMM -> 'CUSTO MEDIO MM/AAAA' /
    'QTD INICIAL MM/AAAA'.

    Retorna o df renomeado e a lista dos novos nomes na ordem em que foram
    encontrados (para poder incluí-los no final da ORDEM_FINAL).
    """
    renomear = {}
    novos_nomes_em_ordem = []
    for col in df.columns:
        m = _REGEX_B9.match(col)
        if not m:
            continue
        tipo = m.group("tipo")           # 'C' ou 'Q'
        ano = m.group("ano")
        mes = m.group("mes")
        prefixo = "CUSTO MEDIO" if tipo == "C" else "QTD INICIAL"
        novo_nome = f"{prefixo} {mes}/{ano}"
        renomear[col] = novo_nome
        novos_nomes_em_ordem.append(novo_nome)
    return df.rename(columns=renomear), novos_nomes_em_ordem


def _formatar_numero(x, casas: int) -> str:
    """Formata número com N casas decimais e vírgula como separador decimal."""
    if pd.isna(x):
        return ""
    try:
        return f"{float(x):.{casas}f}".replace(".", ",")
    except (TypeError, ValueError):
        return str(x)


def tratar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()

    # 1) Strip nas colunas de texto (padrão dos outros relatórios).
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype(str).str.strip().replace("nan", "")

    # 2) Renomear fixas.
    df = df.rename(columns=RENOMEAR_FIXAS)

    # 3) Traduzir TIPO MOV.
    if "TIPO MOV" in df.columns:
        df["TIPO MOV"] = df["TIPO MOV"].map(MAPA_TIPOMOV).fillna(df["TIPO MOV"])

    # 4) Renomear as colunas B9 (nomes dinâmicos com base nas datas usadas).
    df, colunas_b9_novas = _renomear_b9(df)

    # 5) Formatar valores numéricos.
    #    O tratamento com strip acima transformou tudo em str; para as colunas
    #    numéricas precisamos converter de volta com pd.to_numeric antes de
    #    reformatar. errors='coerce' garante que valores não numéricos viram NaN.
    cols_quatro_casas = COLS_QUANTIDADE_BASE + colunas_b9_novas

    for col in COLS_MONETARIAS:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 2))

    for col in cols_quatro_casas:
        if col in df.columns:
            valores = pd.to_numeric(df[col], errors="coerce")
            df[col] = valores.map(lambda x: _formatar_numero(x, 4))

    # 6) Ordem final (fixas + as colunas B9 no fim, na ordem encontrada).
    ordem_final = ORDEM_FINAL_FIXA + colunas_b9_novas
    df = df[[c for c in ordem_final if c in df.columns]]

    return df
