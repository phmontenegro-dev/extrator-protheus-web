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


def _consolidar_continuacoes_hist(df: pd.DataFrame) -> pd.DataFrame:
    """
    Reagrupa continuações de histórico à linha "pai" do mesmo documento.

    No Protheus, o campo CT2_HIST é CHAR(40). Quando o texto do histórico passa
    desse limite, o sistema cria linhas adicionais com CT2_DC='4' e valor zero,
    contendo apenas a continuação do texto. Elas não são lançamentos reais —
    servem só para estender o histórico da linha anterior do mesmo documento.

    Esta função:
      1. Ordena por (FILIAL, LOTE, DOC, LINHA) — assim as continuações ficam
         logo após a linha principal correspondente.
      2. Para cada linha com CT2_DC='4', encontra a última linha principal
         (CT2_DC != '4') vista no mesmo (FILIAL, LOTE, DOC) e concatena o
         texto nela.
      3. Remove as linhas com CT2_DC='4' do DataFrame.

    IMPORTANTE: precisa rodar ANTES do split de partida dobrada, para que
    continuações não causem efeitos colaterais na duplicação de linhas.
    """
    if df.empty or "CT2_DC" not in df.columns:
        return df

    df = df.copy()
    df["CT2_DC"] = df["CT2_DC"].astype(str).str.strip()
    df = df.sort_values(
        ["CT2_FILIAL", "CT2_LOTE", "CT2_DOC", "CT2_LINHA"],
        kind="stable",
    ).reset_index(drop=True)

    eh_cont = (df["CT2_DC"] == "4").to_numpy()

    # Usamos listas em vez de .at/.iat dentro do loop por performance:
    # em datasets grandes (centenas de milhares de linhas) isso é 50x+ rápido.
    filiais = df["CT2_FILIAL"].astype(str).tolist()
    lotes = df["CT2_LOTE"].astype(str).tolist()
    docs = df["CT2_DOC"].astype(str).tolist()
    hists = df["CT2_HIST"].astype(str).tolist()

    ancora_por_grupo: dict[tuple[str, str, str], int] = {}
    for i in range(len(df)):
        chave = (filiais[i], lotes[i], docs[i])
        if eh_cont[i]:
            ancora = ancora_por_grupo.get(chave)
            if ancora is not None:
                # Concatena sem separador — o Protheus corta exatamente no
                # 40º char e a continuação começa no 41º, sem espaço.
                hists[ancora] = (hists[ancora] or "") + (hists[i] or "")
        else:
            ancora_por_grupo[chave] = i

    df["CT2_HIST"] = hists
    df = df[~eh_cont].reset_index(drop=True)
    return df


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

    # Consolida continuações do histórico (CT2_DC='4') nas linhas pai.
    # Precisa rodar antes de TUDO: lotes excluídos não afetam, e precisamos
    # das continuações agregadas antes do split de partida dobrada.
    df = _consolidar_continuacoes_hist(df)

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

    # Remove duplicatas 100% idênticas. Isso costuma acontecer quando o JOIN
    # com CV3 retorna múltiplas linhas para o mesmo lançamento (ex: vários
    # registros de rastreamento apontando para o mesmo RECNO da CT2). Como
    # comparamos TODAS as colunas finais, linhas legítimas com NFs diferentes
    # não são afetadas — só as que são cópias exatas.
    df_final = df_final.drop_duplicates().reset_index(drop=True)

    return df_final
