"""Tratamento das colunas do relatório produtivo por lote."""
from decimal import Decimal

import pandas as pd


RENOMEAR = {
    "FILIAL": "FILIAL",
    "FORNECEDOR": "CÓDIGO DO FORNECEDOR",
    "CLIENTE": "CÓDIGO DO CLIENTE",
    "NOME_CLIENTE": "NOME DO CLIENTE",
    "LOJA": "LOJA DO CLIENTE",
    "COD_PRODUTO": "CÓDIGO DO PRODUTO",
    "TIPO_PRODUTO": "TIPO DO PRODUTO",
    "DESCRICAO_PROD": "DESCRIÇÃO DO PRODUTO",
    "UNIDADE_MEDIDA": "UNIDADE DE MEDIDA",
    "ARMAZEM": "ARMAZÉM",
    "ENDERECO": "ENDEREÇO",
    "QNTD_RECEBIDA": "QUANTIDADE RECEBIDA",
    "QNTD_DO_LOTE": "SALDO DO LOTE",
    "QNTD_EMPENHO": "QUANTIDADE EMPENHADA",
    "QNTD_ORIGINAL": "QUANTIDADE ORIGINAL",
    "OP": "OP",
    "STATUS_OP": "STATUS DA OP",
    "DATA_PREV_INICIO": "DATA PREVISTA DE INÍCIO",
    "DATA_PREV_FINAL": "DATA PREVISTA DE TÉRMINO",
    "OP_PAI": "OP PAI",
    "PRODUTO_PAI": "CÓDIGO DO PRODUTO PAI",
    "LOTE": "LOTE",
    "LOTE_LIDO": "LOTE LIDO",
    "BOBINA_02A": "BOBINA 02A",
    "RECURSO": "CÓDIGO DO RECURSO",
    "DESC_RECURSO": "DESCRIÇÃO DO RECURSO",
    "OPERACAO": "CÓDIGO DA OPERAÇÃO",
    "DESC_OPERACAO": "DESCRIÇÃO DA OPERAÇÃO",
    "ROTEIRO": "CÓDIGO DO ROTEIRO",
    "DESC_ROTEIRO": "DESCRIÇÃO DO ROTEIRO",
    "OPERADOR": "OPERADOR",
    "DATA_APONT": "DATA DO APONTAMENTO",
    "DATA_HORA_INICIAL": "DATA E HORA DE INÍCIO",
    "DATA_HORA_FINAL": "DATA E HORA DE TÉRMINO",
    "TEMPO_REAL": "TEMPO REAL",
    "QNTD_PRODUZIDA": "QUANTIDADE PRODUZIDA",
    "QNTD_PERDA": "QUANTIDADE PERDIDA",
    "PESO_BRUTO": "PESO BRUTO",
    "PESO_LIQUIDO": "PESO LÍQUIDO",
    "PESO_BRUTO_TON": "PESO BRUTO (T)",
    "PESO_LIQUIDO_TON": "PESO LÍQUIDO (T)",
    "DIAMETRO": "DIÂMETRO",
    "METRAGEM": "METRAGEM",
    "M2": "ÁREA (M²)",
    "EMENDAS": "EMENDAS",
    "TIRADAS": "TIRADAS",
    "FOLHA_BOBINA": "FOLHA OU BOBINA",
    "LARGURA_LOTELID": "LARGURA DO LOTE LIDO",
    "GRAMATURA_LOTELIDO": "GRAMATURA DO LOTE LIDO",
    "GRAM_PE1_LOTELIDO": "GRAMATURA PE1 DO LOTE LIDO",
    "GRAM_PE2_LOTELIDO": "GRAMATURA PE2 DO LOTE LIDO",
    "GRAM_PE3_LOTELIDO": "GRAMATURA PE3 DO LOTE LIDO",
    "LARGURA_FINAL": "LARGURA FINAL",
    "COMPRIMENTO": "COMPRIMENTO",
    "GRAMATURA": "GRAMATURA FINAL",
    "GRAM_PE1": "GRAMATURA PE1 FINAL",
    "GRAM_PE2": "GRAMATURA PE2 FINAL",
    "GRAM_PE3": "GRAMATURA PE3 FINAL",
    "QNTD_FATURADA": "QUANTIDADE FATURADA",
    "DATA_EMISSAO": "DATA DE EMISSÃO DA NF DE SAÍDA",
    "VALOR_VENDA": "VALOR DA VENDA",
    "PEDIDO_VENDA": "PEDIDO DE VENDA",
    "NF_SAIDA": "NF DE SAÍDA",
    "ITEM_NF_SAIDA": "ITEM DO PEDIDO DE VENDA",
    "SERIE_NF_SAIDA": "SÉRIE DA NF DE SAÍDA",
    "CODIGO_FISCAL": "CÓDIGO FISCAL",
    "CUSTO": "CUSTO",
    "PEDIDO_ITEM_COMPRA_SUZ": "PEDIDO/ITEM DE COMPRA SUZANO",
    "TIPO_ENTRADA": "TIPO DE ENTRADA",
    "PEDIDO_COMPRA": "PEDIDO DE COMPRA",
    "NF_ENTRADA": "NF DE ENTRADA",
    "DATA_EMISSAO_ENTRADA": "DATA DE EMISSÃO DA NF DE ENTRADA",
}

COLS_DATA = [
    RENOMEAR[col]
    for col in (
        "DATA_PREV_INICIO", "DATA_PREV_FINAL", "DATA_APONT",
        "DATA_HORA_INICIAL", "DATA_HORA_FINAL", "DATA_EMISSAO",
        "DATA_EMISSAO_ENTRADA",
    )
]

COLS_NUMERO = [
    RENOMEAR[col]
    for col in (
        "QNTD_RECEBIDA", "QNTD_DO_LOTE", "QNTD_EMPENHO", "QNTD_ORIGINAL",
        "QNTD_PRODUZIDA", "QNTD_PERDA", "PESO_BRUTO", "PESO_LIQUIDO",
        "PESO_BRUTO_TON", "PESO_LIQUIDO_TON", "DIAMETRO", "METRAGEM", "M2",
        "EMENDAS", "TIRADAS", "LARGURA_LOTELID", "GRAMATURA_LOTELIDO",
        "GRAM_PE1_LOTELIDO", "GRAM_PE2_LOTELIDO", "GRAM_PE3_LOTELIDO",
        "LARGURA_FINAL", "COMPRIMENTO", "GRAMATURA", "GRAM_PE1",
        "GRAM_PE2", "GRAM_PE3", "QNTD_FATURADA", "VALOR_VENDA", "CUSTO",
    )
]

ORDEM_FINAL = list(RENOMEAR.values())


def _formatar_data(valor: str) -> str:
    data, _, hora = valor.partition(" ")
    if len(data) != 8 or not data.isdigit():
        return valor

    data_formatada = f"{data[6:8]}/{data[4:6]}/{data[:4]}"
    hora = hora.strip()
    if not hora:
        return data_formatada
    if len(hora) == 5 and hora[2] == ":":
        hora = f"{hora}:00"
    return f"{data_formatada} {hora}"


def _formatar_numero(valor) -> str:
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()
    if isinstance(valor, (int, float, Decimal)):
        texto = format(Decimal(texto), "f")
        if "." in texto:
            texto = texto.rstrip("0").rstrip(".")
    return texto.replace(".", ",")


def tratar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()
    df = df.rename(columns=RENOMEAR)

    for col in df.select_dtypes(include=["object", "string"]).columns:
        if col not in COLS_NUMERO:
            df[col] = df[col].fillna("").astype(str).str.strip()

    for col in COLS_DATA:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip().map(_formatar_data)

    for col in COLS_NUMERO:
        if col in df.columns:
            df[col] = df[col].map(_formatar_numero)

    df = df[[col for col in ORDEM_FINAL if col in df.columns]]
    return df.drop_duplicates().reset_index(drop=True)