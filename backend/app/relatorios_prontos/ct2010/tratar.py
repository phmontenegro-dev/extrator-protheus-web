"""
Tratamento do CT2010 — reescrita array-based.

Antes trabalhava sobre pandas.DataFrame o tempo todo. Em datasets grandes
(886k+ linhas, 25 colunas object), operações que iteram célula por célula
em pandas (sort_values, drop_duplicates, df.loc[mask], concat, groupby.agg
em muitas colunas) viram O(linhas × colunas) de cópia em Python puro e
derrubam a extração via watchdog.

A estratégia desta versão:
  - Converter o DataFrame em `dict[str, np.ndarray]` logo na entrada
  - Fazer TODAS as operações em arrays numpy (fancy indexing, boolean mask,
    concatenate — tudo vetorizado em C)
  - Usar pandas somente onde é sabidamente vetorizado (.str.strip, .map,
    .to_numeric, DataFrame.duplicated)
  - Montar o DataFrame final só no último passo

Benchmark informal em 886k linhas × 25 colunas: >15min → ~15s.

Semântica preservada em 100%: o resultado é idêntico ao do tratamento
antigo pra os casos cobertos pelos testes (arquivo de referência de
7 linhas, inclusive continuações de histórico em grupos não-contíguos).
"""
from __future__ import annotations

import logging
import time

import numpy as np
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
# lançamento contábil foi gerado a partir de várias NFs). Concatenadas
# pelo _consolidar_nfs_arrays().
_COLS_NF_CONCAT = [
    "TIPO_OPERACAO",
    "NUMERO_NF",
    "SERIE_NF",
    "CLI_FOR",
    "LOJA",
    "NOME_CLIFOR",
    "RAZAO_SOCIAL",
]

# Colunas que precisam de strip explícito. Pulamos as que o único uso é
# comparação via Categorical (FILIAL/DOC/LINHA no sort — codes usam a
# string crua e qualquer diferença entre strip/não é consistente ao longo
# da coluna, não há mistura).
_COLS_STRIP = [
    "CT2_DC", "CT2_LOTE", "CT2_DEBITO", "CT2_CREDIT",
    "CT2_HIST", "CT2_CCD", "CT2_CCC", "CT2_DATA",
    "TIPO_OPERACAO", "NUMERO_NF", "SERIE_NF",
    "CLI_FOR", "LOJA", "NOME_CLIFOR", "RAZAO_SOCIAL",
]


# ---------------------------------------------------------------------------
# API pública (mantida compat com o runner e com uso síncrono)
# ---------------------------------------------------------------------------

def tratar_dataframe(df: pd.DataFrame, ctx=None) -> pd.DataFrame:
    """
    Pipeline de tratamento do CT2010.

    `ctx` é opcional pra manter compat com usos síncronos (fora de job):
    quando presente, batemos `ctx.heartbeat()` entre fases pra evitar
    falso positivo do watchdog em datasets grandes.
    """
    def _bater():
        if ctx is not None:
            try:
                ctx.heartbeat()
            except Exception:
                pass

    def _marco(nome: str, t0: float, qtd: int | None = None):
        dt = time.monotonic() - t0
        if qtd is None:
            log.warning("[CT2010 DIAG] %s em %.1fs", nome, dt)
        else:
            log.warning("[CT2010 DIAG] %s em %.1fs (%d linhas)", nome, dt, qtd)

    # ----- Entrada: converte pra dict de arrays -----
    t = time.monotonic()
    df.columns = df.columns.str.strip()
    cols: dict[str, np.ndarray] = {c: df[c].to_numpy() for c in df.columns}
    n_inicial = len(df)
    _marco("tratar.to_arrays", t, n_inicial)
    _bater()

    # ----- Strip de colunas de string -----
    t = time.monotonic()
    for c in _COLS_STRIP:
        if c in cols:
            cols[c] = pd.Series(cols[c]).astype(str).str.strip().to_numpy()
    _marco("tratar.strip_cols", t, n_inicial)
    _bater()

    # ----- Consolida continuações do histórico (CT2_DC='4') -----
    cols = _consolidar_continuacoes_hist_arrays(cols, _marco)
    _bater()

    # ----- Consolida NFs (agrupa por CT2_RECNO) -----
    cols = _consolidar_nfs_arrays(cols, _marco)
    _bater()

    # ----- Exclui lotes -----
    t = time.monotonic()
    if "CT2_LOTE" in cols:
        keep = ~np.isin(cols["CT2_LOTE"], LOTES_EXCLUIDOS)
        cols = {c: a[keep] for c, a in cols.items()}
    _marco("tratar.excluir_lotes", t, len(next(iter(cols.values()))))
    _bater()

    # ----- Tradução 1/2/3 -> DEBITO/CREDITO/PARTIDA DOBRADA -----
    t = time.monotonic()
    dc = cols["CT2_DC"]
    # np.where aninhado é vetorizado em C.
    traducao = np.where(
        dc == "1", "DEBITO",
        np.where(
            dc == "2", "CREDITO",
            np.where(dc == "3", "PARTIDA DOBRADA", dc),
        ),
    ).astype(object)
    cols["CT2_DC"] = traducao
    _marco("tratar.mapa_dc", t)

    # ----- Split de partida dobrada -----
    cols = _split_partida_dobrada_arrays(cols, _marco)
    _bater()

    # ----- Valor contábil: negativo nos créditos + formato PT-BR -----
    t = time.monotonic()
    valor = pd.to_numeric(pd.Series(cols["CT2_VALOR"]), errors="coerce").to_numpy()
    dc = cols["CT2_DC"]
    valor = np.where(dc == "CREDITO", -np.abs(valor), valor)
    # Formato "x,yz": vetorizar com numpy não é trivial pra float→string
    # com vírgula; loop python é O(n) ~ 1s/M. Aceitável.
    cols["VALOR CONTABIL"] = np.array(
        [f"{v:.2f}".replace(".", ",") if not pd.isna(v) else "" for v in valor],
        dtype=object,
    )
    del cols["CT2_VALOR"]
    _marco("tratar.formatar_valor", t, len(valor))
    _bater()

    # ----- Data: AAAAMMDD → DD/MM/AAAA -----
    t = time.monotonic()
    datas = cols["CT2_DATA"]
    cols["CT2_DATA"] = np.array(
        [f"{d[6:8]}/{d[4:6]}/{d[0:4]}" if isinstance(d, str) and len(d) == 8 else d for d in datas],
        dtype=object,
    )
    _marco("tratar.formatar_data", t)
    _bater()

    # ----- Enriquecer com plano de contas e centro de custo -----
    cols = _enriquecer_arrays(cols, _marco)
    _bater()

    # ----- Seleciona colunas finais na ordem certa -----
    t = time.monotonic()
    cols = {c: cols[c] for c in COLUNAS_FINAIS if c in cols}
    n_pre_dedup = len(next(iter(cols.values()))) if cols else 0
    _marco("tratar.sel_colunas_finais", t, n_pre_dedup)

    # ----- Drop duplicates -----
    cols = _drop_duplicates_arrays(cols, _marco)
    _bater()

    # ----- Monta DataFrame final (passo único, barato) -----
    t = time.monotonic()
    df_final = pd.DataFrame(cols)
    _marco("tratar.montar_df_final", t, len(df_final))
    _bater()

    return df_final


# ---------------------------------------------------------------------------
# Helpers internos — todas as funções abaixo trabalham em dict[str, ndarray].
# ---------------------------------------------------------------------------

def _consolidar_continuacoes_hist_arrays(
    cols: dict[str, np.ndarray], _marco
) -> dict[str, np.ndarray]:
    """
    Reagrupa continuações de histórico (CT2_DC='4') na linha pai do mesmo
    documento. Ver docstring da versão legada abaixo.
    """
    if "CT2_DC" not in cols or len(cols["CT2_DC"]) == 0:
        return cols

    t0 = time.monotonic()
    n = len(cols["CT2_DC"])

    # Ordena por (FILIAL, LOTE, DOC, LINHA) via lexsort de códigos categoricos.
    f_codes = pd.Categorical(cols["CT2_FILIAL"]).codes
    l_codes = pd.Categorical(cols["CT2_LOTE"]).codes
    d_codes = pd.Categorical(cols["CT2_DOC"]).codes
    ln_codes = pd.Categorical(cols["CT2_LINHA"]).codes
    order = np.lexsort((ln_codes, d_codes, l_codes, f_codes))

    filiais_s = cols["CT2_FILIAL"][order]
    lotes_s = cols["CT2_LOTE"][order]
    docs_s = cols["CT2_DOC"][order]
    hists_s = cols["CT2_HIST"][order].copy()  # vamos mutar
    dc_s = cols["CT2_DC"][order]
    eh_cont_s = (dc_s == "4")

    # Loop: âncora é o índice SORTED do último não-continuação visto no
    # mesmo grupo (FILIAL, LOTE, DOC).
    ancora: dict[tuple, int] = {}
    for i in range(n):
        chave = (filiais_s[i], lotes_s[i], docs_s[i])
        if eh_cont_s[i]:
            a = ancora.get(chave)
            if a is not None:
                # Protheus corta no 40º char; continuação começa no 41º sem espaço.
                hists_s[a] = (hists_s[a] or "") + (hists_s[i] or "")
        else:
            ancora[chave] = i

    # Devolve HIST pro índice original e filtra as linhas de continuação.
    hists_final = np.empty(n, dtype=object)
    hists_final[order] = hists_s
    eh_cont_orig = np.zeros(n, dtype=bool)
    eh_cont_orig[order] = eh_cont_s
    keep = ~eh_cont_orig

    new_cols = {c: a[keep] for c, a in cols.items()}
    new_cols["CT2_HIST"] = hists_final[keep]
    _marco("tratar.consolidar_continuacoes_hist", t0, len(new_cols["CT2_DC"]))
    return new_cols


def _consolidar_nfs_arrays(
    cols: dict[str, np.ndarray], _marco
) -> dict[str, np.ndarray]:
    """
    Agrupa linhas duplicadas pelo JOIN com CV3/SF1/SF2 (mesmo CT2_RECNO)
    concatenando as colunas de NF. Mantém a primeira ocorrência das demais
    colunas (que já são idênticas no grupo).
    """
    if "CT2_RECNO" not in cols or len(cols["CT2_RECNO"]) == 0:
        return cols

    t0 = time.monotonic()
    recno = cols["CT2_RECNO"]
    n = len(recno)

    # Agrupa índices por RECNO mantendo ordem de primeira aparição.
    # Uma volta Python pura em ~886k iters é ~0.2-0.5s.
    groups: dict[object, list[int]] = {}
    for i in range(n):
        r = recno[i]
        if r not in groups:
            groups[r] = [i]
        else:
            groups[r].append(i)

    primeiros = np.fromiter(
        (v[0] for v in groups.values()), dtype=np.int64, count=len(groups),
    )

    # Filtra todos os arrays pelos primeiros índices (fancy index numpy).
    new_cols = {c: a[primeiros] for c, a in cols.items()}

    # Pra cada coluna NF, substitui o valor do primeiro pela concatenação
    # dos valores únicos não-vazios ("nan"/"None" descartados).
    for col_nf in _COLS_NF_CONCAT:
        if col_nf not in cols:
            continue
        arr = cols[col_nf]
        novo_arr = new_cols[col_nf].copy()  # vamos mutar posição a posição
        for idx_novo, (_r, indices) in enumerate(groups.items()):
            if len(indices) == 1:
                continue
            vistos: list[str] = []
            for i in indices:
                v = arr[i]
                if v is None:
                    continue
                s = str(v).strip()
                if not s or s.lower() in ("nan", "none"):
                    continue
                if s not in vistos:
                    vistos.append(s)
            novo_arr[idx_novo] = ", ".join(vistos)
        new_cols[col_nf] = novo_arr

    _marco("tratar.consolidar_nfs", t0, len(new_cols["CT2_RECNO"]))
    return new_cols


def _split_partida_dobrada_arrays(
    cols: dict[str, np.ndarray], _marco
) -> dict[str, np.ndarray]:
    """
    Linhas com CT2_DC == 'PARTIDA DOBRADA' viram duas: uma DEBITO (CT2_CREDIT
    e CT2_CCC vazios) e uma CREDITO (CT2_DEBITO e CT2_CCD vazios). As demais
    colunas são copiadas iguais.
    """
    t0 = time.monotonic()
    dc = cols["CT2_DC"]
    mask_pd = (dc == "PARTIDA DOBRADA")
    n_pd = int(mask_pd.sum())
    if n_pd == 0:
        _marco("tratar.split_partida_dobrada", t0, len(dc))
        return cols

    idx_pd = np.where(mask_pd)[0]
    idx_nao_pd = np.where(~mask_pd)[0]

    # Pra cada coluna, concatena: [não-pd, pd-debito, pd-credito]
    new_cols: dict[str, np.ndarray] = {}
    vazio_pd = np.full(n_pd, "", dtype=object)
    for c, arr in cols.items():
        nao = arr[idx_nao_pd]
        pd_arr = arr[idx_pd]
        if c == "CT2_CREDIT":
            new_cols[c] = np.concatenate([nao, vazio_pd, pd_arr])
        elif c == "CT2_CCC":
            new_cols[c] = np.concatenate([nao, vazio_pd, pd_arr])
        elif c == "CT2_DEBITO":
            new_cols[c] = np.concatenate([nao, pd_arr, vazio_pd])
        elif c == "CT2_CCD":
            new_cols[c] = np.concatenate([nao, pd_arr, vazio_pd])
        elif c == "CT2_DC":
            new_cols[c] = np.concatenate([
                nao,
                np.full(n_pd, "DEBITO", dtype=object),
                np.full(n_pd, "CREDITO", dtype=object),
            ])
        else:
            new_cols[c] = np.concatenate([nao, pd_arr, pd_arr])

    _marco("tratar.split_partida_dobrada", t0, len(new_cols["CT2_DC"]))
    return new_cols


def _enriquecer_arrays(
    cols: dict[str, np.ndarray], _marco
) -> dict[str, np.ndarray]:
    """
    Enriquecimento: CONTA CONTABIL + PACOTE + DESCRICAO_CONTA (pelo mapa
    de plano de contas) e CENTRO DE CUSTO + RESPONSAVEL + DESC_CC +
    CUSTO_DESPESA (pelo mapa de centro de custo).
    """
    t0 = time.monotonic()
    mapa_pacote, mapa_desc_conta = carregar_plano_contas()
    mapa_resp, mapa_desc_cc, mapa_custo_despesa = carregar_centro_custo()

    # CONTA CONTABIL = CT2_DEBITO se não for vazio depois do strip, senão CT2_CREDIT.
    deb = cols["CT2_DEBITO"]
    cre = cols["CT2_CREDIT"]
    # Cuidado: os arrays já foram strip-ados no começo do pipeline, mas
    # por segurança aplicamos de novo (barato se já é string limpo).
    deb_stripped = pd.Series(deb).astype(str).str.strip().to_numpy()
    is_empty = (deb_stripped == "")
    conta = np.where(is_empty, cre, deb)
    cols["CONTA CONTABIL"] = conta

    conta_key = pd.Series(conta).astype(str).str.strip()
    cols["PACOTE"] = conta_key.map(mapa_pacote).to_numpy()
    cols["DESCRICAO_CONTA"] = conta_key.map(mapa_desc_conta).to_numpy()

    ccd = cols["CT2_CCD"]
    ccc = cols["CT2_CCC"]
    ccd_stripped = pd.Series(ccd).astype(str).str.strip().to_numpy()
    is_empty_cc = (ccd_stripped == "")
    cc = np.where(is_empty_cc, ccc, ccd)
    cols["CENTRO DE CUSTO"] = cc

    cc_key = pd.Series(cc).astype(str).str.strip()
    cols["RESPONSAVEL"] = cc_key.map(mapa_resp).to_numpy()
    cols["DESC_CC"] = cc_key.map(mapa_desc_cc).to_numpy()
    cols["CUSTO_DESPESA"] = cc_key.map(mapa_custo_despesa).to_numpy()

    _marco("tratar.enriquecer", t0)
    return cols


def _drop_duplicates_arrays(
    cols: dict[str, np.ndarray], _marco
) -> dict[str, np.ndarray]:
    """
    Drop duplicates comparando TODAS as colunas. Usa DataFrame.duplicated(),
    que é interno em C — único passo em que o pandas inteiro é explicitado.
    O custo de montar o DF temporário com arrays prontos é ~instantâneo
    (nenhuma cópia por célula, só o BlockManager apontando pros arrays).
    """
    t0 = time.monotonic()
    df_tmp = pd.DataFrame(cols)
    keep = (~df_tmp.duplicated()).to_numpy()
    new_cols = {c: a[keep] for c, a in cols.items()}
    _marco("tratar.drop_duplicates", t0, len(next(iter(new_cols.values()))))
    return new_cols


# ---------------------------------------------------------------------------
# Compat: mantém as funções legadas do módulo pra quem importa diretamente.
# A principal é `enriquecer_dataframe`, chamada por testes de desktop.
# ---------------------------------------------------------------------------

def enriquecer_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Versão DataFrame-friendly do enriquecimento (compat com código antigo)."""
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


def _concat_unicos(serie: pd.Series) -> str:
    """Helper legado — mantido pra compat se algum teste importar direto."""
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
    """Compat: versão DataFrame do consolidar_nfs. Usada se alguém importar diretamente."""
    if df.empty or "CT2_RECNO" not in df.columns:
        return df
    cols = {c: df[c].to_numpy() for c in df.columns}
    cols = _consolidar_nfs_arrays(cols, lambda *a, **k: None)
    return pd.DataFrame(cols)


def _consolidar_continuacoes_hist(df: pd.DataFrame) -> pd.DataFrame:
    """Compat: versão DataFrame do consolidar_continuacoes_hist."""
    if df.empty or "CT2_DC" not in df.columns:
        return df
    cols = {c: df[c].to_numpy() for c in df.columns}
    # Strip de CT2_DC pra bater com a lógica original.
    cols["CT2_DC"] = pd.Series(cols["CT2_DC"]).astype(str).str.strip().to_numpy()
    cols["CT2_HIST"] = pd.Series(cols["CT2_HIST"]).astype(str).to_numpy()
    cols = _consolidar_continuacoes_hist_arrays(cols, lambda *a, **k: None)
    return pd.DataFrame(cols)
