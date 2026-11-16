"""
Tratamento do CT2010 — portado do desktop, importando apoio do mesmo pacote.
"""
import pandas as pd

from app.relatorios_prontos.ct2010.apoio import carregar_plano_contas, carregar_centro_custo


COLUNAS_FINAIS = [
    "CT2_FILIAL",  "CT2_LOTE", "CT2_DOC", "CT2_DC",
    "CONTA CONTABIL", "PACOTE", "DESCRICAO_CONTA", "VALOR CONTABIL",
    "CT2_HIST",
    "TIPO_OPERACAO", "NUMERO_NF", "SERIE_NF",
    "CLI_FOR", "LOJA", "NOME_CLIFOR", "RAZAO_SOCIAL",
    "CT2_ITEMD", "CENTRO DE CUSTO", "RESPONSAVEL", "DESC_CC", "CUSTO_DESPESA",
    "CT2_ITEMC", "CT2_CLVLDB", "CT2_CLVLCR", "CT2_ORIGEM", "CT2_DATA", "CT2_LINHA",
]

MAPA_DC = {
    "1": "DEBITO", 1: "DEBITO",
    "2": "CREDITO", 2: "CREDITO",
    "3": "PARTIDA DOBRADA", 3: "PARTIDA DOBRADA",
}

LOTES_EXCLUIDOS = [
    "777790",
    "777780",
    "777750",
    "008840",
    "008845",
]


def enriquecer_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    mapa_pacote, mapa_desc_conta = carregar_plano_contas()
    mapa_resp, mapa_desc_cc, mapa_custo_despesa = carregar_centro_custo()

    df["CONTA CONTABIL"] = df["CT2_DEBITO"].where(
        df["CT2_DEBITO"].str.strip() != "", df["CT2_CREDIT"]
    )
    chave_conta = df["CONTA CONTABIL"].astype(str).str.strip()
    df["PACOTE"] = chave_conta.map(mapa_pacote)
    df["DESCRICAO_CONTA"] = chave_conta.map(mapa_desc_conta)

    df["CENTRO DE CUSTO"] = df["CT2_CCD"].where(
        df["CT2_CCD"].str.strip() != "", df["CT2_CCC"]
    )
    chave_cc = df["CENTRO DE CUSTO"].astype(str).str.strip()
    df["RESPONSAVEL"] = chave_cc.map(mapa_resp)
    df["DESC_CC"] = chave_cc.map(mapa_desc_cc)
    df["CUSTO_DESPESA"] = chave_cc.map(mapa_custo_despesa)

    return df


def tratar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip()

    for col in ["CT2_FILIAL", "CT2_LOTE", "CT2_DEBITO", "CT2_CREDIT",
                "CT2_HIST", "CT2_CCD", "CT2_CCC", "CT2_DATA",
                "TIPO_OPERACAO", "NUMERO_NF", "SERIE_NF",
                "CLI_FOR", "LOJA", "NOME_CLIFOR", "RAZAO_SOCIAL"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Exclusão de lotes
    df = df[~df["CT2_LOTE"].isin(LOTES_EXCLUIDOS)].copy()

    # Tradução 1/2/3 -> DEBITO/CREDITO/PARTIDA DOBRADA
    df["CT2_DC"] = df["CT2_DC"].astype(str).str.strip().map(MAPA_DC).fillna(df["CT2_DC"])

    # Partida dobrada vira duas linhas
    linhas_novas = []
    partida_dobrada = df[df["CT2_DC"] == "PARTIDA DOBRADA"]
    demais = df[df["CT2_DC"] != "PARTIDA DOBRADA"]

    for _, linha in partida_dobrada.iterrows():
        linha_debito = linha.copy()
        linha_debito["CT2_CREDIT"] = ""
        linha_debito["CT2_CCC"] = ""
        linha_debito["CT2_DC"] = "DEBITO"
        linhas_novas.append(linha_debito)

        linha_credito = linha.copy()
        linha_credito["CT2_DEBITO"] = ""
        linha_credito["CT2_CCD"] = ""
        linha_credito["CT2_DC"] = "CREDITO"
        linhas_novas.append(linha_credito)

    df_final = pd.concat([demais, pd.DataFrame(linhas_novas)], ignore_index=True)

    # Sinal negativo nos créditos
    df_final["CT2_VALOR"] = pd.to_numeric(df_final["CT2_VALOR"], errors="coerce")
    df_final.loc[df_final["CT2_DC"] == "CREDITO", "CT2_VALOR"] = -df_final.loc[
        df_final["CT2_DC"] == "CREDITO", "CT2_VALOR"
    ].abs()

    # Ponto -> vírgula no valor
    df_final["VALOR CONTABIL"] = df_final["CT2_VALOR"].map(
        lambda x: f"{x:.2f}".replace(".", ",") if pd.notna(x) else ""
    )
    df_final = df_final.drop(columns=["CT2_VALOR"])

    # Data AAAAMMDD -> DD/MM/AAAA
    df_final["CT2_DATA"] = df_final["CT2_DATA"].apply(
        lambda d: f"{d[6:8]}/{d[4:6]}/{d[0:4]}" if isinstance(d, str) and len(d) == 8 else d
    )

    df_final = enriquecer_dataframe(df_final)
    df_final = df_final[[c for c in COLUNAS_FINAIS if c in df_final.columns]]
    return df_final
