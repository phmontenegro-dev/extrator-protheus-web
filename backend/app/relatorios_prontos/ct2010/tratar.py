"""
Tratamento do CT2010 — portado do desktop, importando apoio do mesmo pacote.
"""
import logging
import time

import pandas as pd

from app.relatorios_prontos.ct2010.apoio import carregar_plano_contas, carregar_centro_custo

log = logging.getLogger(__name__)


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


# Colunas que podem ter MÚLTIPLOS valores por lançamento (quando um mesmo
# lançamento contábil foi gerado a partir de várias NFs). São concatenadas
# pelo _consolidar_nfs() pra manter 1 linha por lançamento.
_COLS_NF_CONCAT = [
    "TIPO_OPERACAO",
    "NUMERO_NF",
    "SERIE_NF",
    "CLI_FOR",
    "LOJA",
    "NOME_CLIFOR",
    "RAZAO_SOCIAL",
]


def _concat_unicos(serie: pd.Series) -> str:
    """Concatena valores únicos não-vazios de uma Series com ', ', preservando ordem."""
    vistos: list[str] = []
    for v in serie:
        if v is None:
            continue
        s = str(v).strip()
        if not s or s.lower() in ("nan", "none"):
            continue
        if s not in vistos:
            vistos.append(s)
    return ", ".join(vistos)


def _consolidar_nfs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa linhas que vêm duplicadas pela explosão do JOIN em CV3/SF1/SF2,
    concatenando as colunas de NF em uma única célula por lançamento.

    Causa raiz: um lançamento contábil pode ter sido gerado por mais de uma
    NF (ex: boleto que paga 3 NFs → 1 registro em CT2010 + 3 em CV3010). A
    extração traz 3 linhas idênticas do CT2 com NFs diferentes, o que
    inflaciona o valor contábil quando somado.

    Esta função agrupa por CT2_RECNO (identificador único do lançamento) e:
      - concatena com ', ' as colunas de NF (TIPO_OPERACAO, NUMERO_NF, SERIE_NF,
        CLI_FOR, LOJA, NOME_CLIFOR, RAZAO_SOCIAL)
      - mantém o primeiro valor das demais colunas (que são idênticas no grupo)

    Precisa rodar ANTES do split de partida dobrada — senão agruparia o
    "DEBITO" com o "CREDITO" gerados do mesmo lançamento.
    """
    if df.empty or "CT2_RECNO" not in df.columns:
        return df

    df = df.copy()
    # Normaliza colunas de NF pra evitar "nan"/"None" como string
    for c in _COLS_NF_CONCAT:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip().replace({"nan": "", "None": ""})

    # Separa colunas: as de NF concatenam, as demais pegam a primeira (idênticas no grupo)
    cols_concat = [c for c in _COLS_NF_CONCAT if c in df.columns]
    cols_first = [c for c in df.columns if c not in cols_concat and c != "CT2_RECNO"]

    agg_map: dict[str, object] = {c: "first" for c in cols_first}
    for c in cols_concat:
        agg_map[c] = _concat_unicos

    # groupby com sort=False preserva a ordem de aparição das linhas no df.
    df_agg = df.groupby("CT2_RECNO", sort=False, as_index=False).agg(agg_map)
    return df_agg


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

    import numpy as np
    t0 = time.monotonic()

    # Normaliza CT2_DC in-place (não copia o DataFrame todo).
    df["CT2_DC"] = df["CT2_DC"].astype(str).str.strip()
    log.warning(
        "[CT2010 DIAG] cont_hist.dc_strip em %.1fs (%d linhas)",
        time.monotonic() - t0, len(df),
    )

    # Extrai apenas as colunas que o loop usa como ARRAYS numpy. Nunca
    # reordenamos o DataFrame inteiro (seria O(linhas × colunas) de cópia
    # pandas em object dtype — minutos em 886k × 25). Trabalhamos só com
    # as 5 colunas em arrays, achamos a ordem, aplicamos o resultado de
    # volta via índice.
    t = time.monotonic()
    filiais_orig = df["CT2_FILIAL"].to_numpy()
    lotes_orig = df["CT2_LOTE"].to_numpy()
    docs_orig = df["CT2_DOC"].to_numpy()
    linhas_orig = df["CT2_LINHA"].to_numpy()
    hists_orig = df["CT2_HIST"].astype(str).to_numpy()
    dc_orig = df["CT2_DC"].to_numpy()
    log.warning(
        "[CT2010 DIAG] cont_hist.to_numpy em %.1fs",
        time.monotonic() - t,
    )

    # Códigos categoricos pra comparar como int (lexsort em string é lento).
    t = time.monotonic()
    f_codes = pd.Categorical(filiais_orig).codes
    l_codes = pd.Categorical(lotes_orig).codes
    d_codes = pd.Categorical(docs_orig).codes
    ln_codes = pd.Categorical(linhas_orig).codes
    log.warning(
        "[CT2010 DIAG] cont_hist.cat_codes em %.1fs",
        time.monotonic() - t,
    )

    # lexsort: a ÚLTIMA chave tem prioridade MAIOR, então inverte a ordem
    # pra manter o mesmo comportamento do antigo sort_values.
    t = time.monotonic()
    order = np.lexsort((ln_codes, d_codes, l_codes, f_codes))
    log.warning(
        "[CT2010 DIAG] cont_hist.lexsort em %.1fs",
        time.monotonic() - t,
    )

    # Reindexa só os arrays (não o DataFrame).
    t = time.monotonic()
    filiais_s = filiais_orig[order]
    lotes_s = lotes_orig[order]
    docs_s = docs_orig[order]
    hists_s = hists_orig[order].copy()  # .copy() porque vamos mutar
    dc_s = dc_orig[order]
    eh_cont_s = (dc_s == "4")
    log.warning(
        "[CT2010 DIAG] cont_hist.reindex_arrays em %.1fs",
        time.monotonic() - t,
    )

    # Loop em ordem — âncora é o índice SORTED. Como estamos iterando em
    # ordem lexicográfica (FILIAL, LOTE, DOC, LINHA), a âncora é sempre
    # a última linha "não-continuação" vista no mesmo grupo (FILIAL, LOTE,
    # DOC) — exatamente o que queremos.
    t = time.monotonic()
    n = len(df)
    ancora_por_grupo: dict[tuple, int] = {}
    for i in range(n):
        chave = (filiais_s[i], lotes_s[i], docs_s[i])
        if eh_cont_s[i]:
            ancora = ancora_por_grupo.get(chave)
            if ancora is not None:
                # Protheus corta no 40º char; continuação começa no 41º sem espaço.
                hists_s[ancora] = (hists_s[ancora] or "") + (hists_s[i] or "")
        else:
            ancora_por_grupo[chave] = i
    log.warning(
        "[CT2010 DIAG] cont_hist.loop em %.1fs (%d linhas)",
        time.monotonic() - t, n,
    )

    # Reescreve CT2_HIST no DataFrame original (sem reordenar o df).
    # hists_s está na ordem SORTED; precisamos mapear de volta pra ordem
    # original usando `order` como tabela de permutação: hists_final[order[i]] = hists_s[i].
    t = time.monotonic()
    hists_final = np.empty(n, dtype=object)
    hists_final[order] = hists_s
    df["CT2_HIST"] = hists_final

    # eh_cont no DataFrame original: desfaz o order também.
    eh_cont_orig = np.zeros(n, dtype=bool)
    eh_cont_orig[order] = eh_cont_s
    df = df.loc[~eh_cont_orig].reset_index(drop=True)
    log.warning(
        "[CT2010 DIAG] cont_hist.writeback em %.1fs (%d linhas finais)",
        time.monotonic() - t, len(df),
    )
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


def tratar_dataframe(df: pd.DataFrame, ctx=None) -> pd.DataFrame:
    """
    Tratamento completo do CT2010.

    `ctx` é opcional pra manter compat com usos síncronos (fora de job):
    quando presente, batemos `ctx.heartbeat()` entre as fases pesadas
    (groupby de consolidação, iterrows de partida dobrada, drop_duplicates
    final). Isso impede que o watchdog marque o job como zumbi em
    datasets grandes (ex: ano inteiro de lançamentos).
    """
    def _bater():
        """Helper local: bate heartbeat se ctx foi passado, senão no-op."""
        if ctx is not None:
            try:
                ctx.heartbeat()
            except Exception:
                pass  # best-effort, nunca derruba o tratamento

    def _marco(nome: str, t0: float, qtd: int | None = None):
        dt = time.monotonic() - t0
        if qtd is None:
            log.warning("[CT2010 DIAG] tratar.%s em %.1fs", nome, dt)
        else:
            log.warning("[CT2010 DIAG] tratar.%s em %.1fs (%d linhas)", nome, dt, qtd)

    t = time.monotonic()
    df = df.copy()
    df.columns = df.columns.str.strip()
    _marco("copy+strip_cols", t, len(df))

    t = time.monotonic()
    for col in ["CT2_FILIAL", "CT2_LOTE", "CT2_DEBITO", "CT2_CREDIT",
                "CT2_HIST", "CT2_CCD", "CT2_CCC", "CT2_DATA",
                "TIPO_OPERACAO", "NUMERO_NF", "SERIE_NF",
                "CLI_FOR", "LOJA", "NOME_CLIFOR", "RAZAO_SOCIAL"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    _marco("astype_strip", t, len(df))
    _bater()

    # Consolida continuações do histórico (CT2_DC='4') nas linhas pai.
    # Precisa rodar antes de TUDO: lotes excluídos não afetam, e precisamos
    # das continuações agregadas antes do split de partida dobrada.
    t = time.monotonic()
    df = _consolidar_continuacoes_hist(df)
    _marco("consolidar_continuacoes_hist", t, len(df))
    _bater()

    # Consolida linhas duplicadas pelo JOIN com CV3 quando um lançamento tem
    # múltiplas NFs. Concatena as colunas de NF em uma única célula por
    # lançamento (ex: "123, 456, 789" no NUMERO_NF). Precisa rodar ANTES do
    # split de partida dobrada — senão agruparia débito e crédito juntos.
    t = time.monotonic()
    df = _consolidar_nfs(df)
    _marco("consolidar_nfs", t, len(df))
    _bater()

    # Exclusão de lotes
    t = time.monotonic()
    df = df[~df["CT2_LOTE"].isin(LOTES_EXCLUIDOS)].copy()
    _marco("excluir_lotes", t, len(df))

    # Tradução 1/2/3 -> DEBITO/CREDITO/PARTIDA DOBRADA
    t = time.monotonic()
    df["CT2_DC"] = df["CT2_DC"].astype(str).str.strip().map(MAPA_DC).fillna(df["CT2_DC"])
    _marco("mapa_dc", t)

    # Partida dobrada vira duas linhas. O iterrows é O(n) python puro e pode
    # ser pesado em bases grandes — batemos heartbeat a cada 10k linhas.
    t = time.monotonic()
    linhas_novas = []
    partida_dobrada = df[df["CT2_DC"] == "PARTIDA DOBRADA"]
    demais = df[df["CT2_DC"] != "PARTIDA DOBRADA"]
    log.warning(
        "[CT2010 DIAG] partida_dobrada separada em %.1fs — %d partidas dobradas, %d demais",
        time.monotonic() - t, len(partida_dobrada), len(demais),
    )

    t = time.monotonic()
    for i, (_, linha) in enumerate(partida_dobrada.iterrows()):
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

        if (i + 1) % 10_000 == 0:
            _bater()
            log.warning(
                "[CT2010 DIAG] iterrows partida_dobrada: %d/%d (%.1fs)",
                i + 1, len(partida_dobrada), time.monotonic() - t,
            )
    _marco("iterrows_partida_dobrada", t, len(linhas_novas))

    t = time.monotonic()
    df_final = pd.concat([demais, pd.DataFrame(linhas_novas)], ignore_index=True)
    _marco("concat_final", t, len(df_final))
    _bater()

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

    t = time.monotonic()
    df_final = enriquecer_dataframe(df_final)
    _marco("enriquecer_dataframe", t, len(df_final))

    t = time.monotonic()
    df_final = df_final[[c for c in COLUNAS_FINAIS if c in df_final.columns]]
    _marco("selecao_colunas_finais", t, len(df_final))
    _bater()

    # Remove duplicatas 100% idênticas. Isso costuma acontecer quando o JOIN
    # com CV3 retorna múltiplas linhas para o mesmo lançamento (ex: vários
    # registros de rastreamento apontando para o mesmo RECNO da CT2). Como
    # comparamos TODAS as colunas finais, linhas legítimas com NFs diferentes
    # não são afetadas — só as que são cópias exatas.
    t = time.monotonic()
    df_final = df_final.drop_duplicates().reset_index(drop=True)
    _marco("drop_duplicates", t, len(df_final))
    _bater()

    return df_final
