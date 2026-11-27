"""
Extração — Produtivo por OP (Produção) — refactor array-based.

Portou toda a agregação pesada do Oracle (CTE `Producao` com 20M rows
virtuais + 7.9GB de temp space + SORT GROUP BY gigante) para pandas/numpy
vetorizado. Oracle agora só faz consultas simples indexadas e devolve
dados crus; Python agrega, cruza, formata.

Mesma estratégia que resolveu o CT2010 (6min+ → 10s).

Pipeline:
  1. Oracle devolve 7 datasets crus (ordens, apontamentos, produtos,
     empenhos, paradas, SG2010, SH1010, SA1010)
  2. Python agrega os apontamentos por OP (SUM, COUNT DISTINCT, MAX ordenado)
  3. Python resolve o Produto final de cada OP (ranking por filial)
  4. Python resolve lookups (SG2010 operação, SH1 recurso, SH1 recurso
     apontado, SA1 cliente) — todos via `.map()` após ranking
  5. Python calcula consumo + tubetes + paradas (merge-overlap)
  6. Python monta o DataFrame final com as mesmas colunas formatadas que
     o SQL original devolvia

Semântica preservada 100%: mesmo critério de preferência filial-específica
sobre genérico, mesmo tiebreak por Recno desc, mesmas regras de paradas
por janela de produção.
"""
from __future__ import annotations

import logging
import time

import numpy as np
import pandas as pd

from app.oracle import get_oracle_connection

log = logging.getLogger(__name__)


# ============================================================================
# Queries SQL — cada uma é indexada e simples. Nenhuma tem CASE WHEN
# aninhado, OUTER APPLY, nem agregações pesadas.
# ============================================================================

# Query 1: ORDENS + APONTAMENTOS joined pelos OPs no período.
# Filtra OPs via DatasPorOP (mesma semântica do SQL original: a janela
# total da OP intersecta o período).
#
# Devolve 1 linha por apontamento (denormalizado com dados da ordem).
_SQL_ORDENS_APONT = """
WITH Parametros AS (
    SELECT TO_DATE(:data_inicio, 'YYYYMMDD') AS di,
           TO_DATE(:data_fim,    'YYYYMMDD') AS df
    FROM dual
),
DatasPorOP AS (
    SELECT H.H6_FILIAL AS Filial, H.H6_OP AS OP,
           MIN(TO_DATE(TRIM(H.H6_DATAINI) DEFAULT NULL ON CONVERSION ERROR,
                       'FXYYYYMMDD')) AS DataInicio,
           MAX(TO_DATE(TRIM(H.H6_DATAFIN) DEFAULT NULL ON CONVERSION ERROR,
                       'FXYYYYMMDD')) AS DataFim
    FROM SH6010 H
    WHERE H.D_E_L_E_T_ = ' '
      AND TRIM(H.H6_OP) IS NOT NULL
    GROUP BY H.H6_FILIAL, H.H6_OP
),
OpsNoPeriodo AS (
    SELECT D.Filial, D.OP
    FROM DatasPorOP D
    CROSS JOIN Parametros P
    WHERE COALESCE(D.DataFim, D.DataInicio) >= P.di
      AND COALESCE(D.DataInicio, D.DataFim) <= P.df
)
SELECT
    O.C2_FILIAL        AS "O_Filial",
    O.C2_OP            AS "O_OP",
    O.C2_PRODUTO       AS "O_Produto",
    O.C2_ROTEIRO       AS "O_Roteiro",
    O.C2_XRECURS       AS "O_Recurso",
    O.C2_XCLIENT       AS "O_Cliente",
    O.C2_XLOJA         AS "O_LojaCliente",
    O.C2_DATPRI        AS "O_DataPrevistaRaw",
    O.C2_QUANT         AS "O_QuantidadePrevista",
    H.H6_OPERAC        AS "H_Operacao",
    H.H6_OPERADO       AS "H_Operador",
    H.H6_RECURSO       AS "H_RecursoApontado",
    H.H6_PRODUTO       AS "H_Produto",
    H.H6_QTDPROD       AS "H_Quantidade",
    H.H6_LOTECTL       AS "H_LoteProduzido",
    H.H6_XLOTELI       AS "H_LoteConsumido",
    H.R_E_C_N_O_       AS "H_Recno",
    H.H6_DATAINI       AS "H_DataIniRaw",
    H.H6_HORAINI       AS "H_HoraIniRaw",
    H.H6_DATAFIN       AS "H_DataFinRaw",
    H.H6_HORAFIN       AS "H_HoraFinRaw"
FROM SC2010 O
JOIN SH6010 H
    ON H.H6_FILIAL = O.C2_FILIAL
   AND H.H6_OP     = O.C2_OP
WHERE O.D_E_L_E_T_ = ' '
  AND H.D_E_L_E_T_ = ' '
  AND TRIM(O.C2_OP) IS NOT NULL
  AND EXISTS (
      SELECT 1 FROM OpsNoPeriodo X
      WHERE X.Filial = O.C2_FILIAL AND X.OP = O.C2_OP
  )
"""

# Query 2: todas as ordens no período, com ou sem apontamentos.
# O JOIN acima perde ordens SEM apontamento (não entram pelo JOIN com SH6010).
# Precisamos delas também pra exibir "NÃO INICIADA" no status.
_SQL_ORDENS_SEM_APONT = """
WITH Parametros AS (
    SELECT TO_DATE(:data_inicio, 'YYYYMMDD') AS di,
           TO_DATE(:data_fim,    'YYYYMMDD') AS df
    FROM dual
),
DatasPorOP AS (
    SELECT H.H6_FILIAL AS Filial, H.H6_OP AS OP,
           MIN(TO_DATE(TRIM(H.H6_DATAINI) DEFAULT NULL ON CONVERSION ERROR,
                       'FXYYYYMMDD')) AS DataInicio,
           MAX(TO_DATE(TRIM(H.H6_DATAFIN) DEFAULT NULL ON CONVERSION ERROR,
                       'FXYYYYMMDD')) AS DataFim
    FROM SH6010 H
    WHERE H.D_E_L_E_T_ = ' '
      AND TRIM(H.H6_OP) IS NOT NULL
    GROUP BY H.H6_FILIAL, H.H6_OP
)
SELECT
    O.C2_FILIAL  AS "Filial",
    O.C2_OP      AS "OP",
    O.C2_PRODUTO AS "Produto",
    O.C2_ROTEIRO AS "Roteiro",
    O.C2_XRECURS AS "Recurso",
    O.C2_XCLIENT AS "Cliente",
    O.C2_XLOJA   AS "LojaCliente",
    O.C2_DATPRI  AS "DataPrevistaRaw",
    O.C2_QUANT   AS "QuantidadePrevista"
FROM SC2010 O
CROSS JOIN Parametros P
LEFT JOIN DatasPorOP D
    ON D.Filial = O.C2_FILIAL AND D.OP = O.C2_OP
WHERE O.D_E_L_E_T_ = ' '
  AND TRIM(O.C2_OP) IS NOT NULL
  AND COALESCE(D.DataFim, D.DataInicio) >= P.di
  AND COALESCE(D.DataInicio, D.DataFim) <= P.df
"""

# Query 3: SB1010 inteira (pequena, ~25k linhas).
_SQL_PRODUTOS = """
SELECT TRIM(B1_FILIAL) AS "Filial", B1_COD AS "Codigo",
       TRIM(B1_UM) AS "UM", RTRIM(B1_DESC) AS "Descricao",
       B1_XLARG AS "Largura", B1_XCOMP AS "Comprimento",
       NVL(B1_XGRAM1, 0) + NVL(B1_XGRAM2, 0) + NVL(B1_XGRAM3, 0) AS "Gramatura",
       R_E_C_N_O_ AS "Recno"
FROM SB1010
WHERE D_E_L_E_T_ = ' '
"""

# Query 4: SD4010 (empenhos) só das OPs no período.
_SQL_EMPENHOS = """
WITH Parametros AS (
    SELECT TO_DATE(:data_inicio, 'YYYYMMDD') AS di,
           TO_DATE(:data_fim,    'YYYYMMDD') AS df
    FROM dual
),
DatasPorOP AS (
    SELECT H.H6_FILIAL AS Filial, H.H6_OP AS OP,
           MIN(TO_DATE(TRIM(H.H6_DATAINI) DEFAULT NULL ON CONVERSION ERROR,
                       'FXYYYYMMDD')) AS DataInicio,
           MAX(TO_DATE(TRIM(H.H6_DATAFIN) DEFAULT NULL ON CONVERSION ERROR,
                       'FXYYYYMMDD')) AS DataFim
    FROM SH6010 H
    WHERE H.D_E_L_E_T_ = ' '
      AND TRIM(H.H6_OP) IS NOT NULL
    GROUP BY H.H6_FILIAL, H.H6_OP
),
OpsNoPeriodo AS (
    SELECT D.Filial, D.OP
    FROM DatasPorOP D
    CROSS JOIN Parametros P
    WHERE COALESCE(D.DataFim, D.DataInicio) >= P.di
      AND COALESCE(D.DataInicio, D.DataFim) <= P.df
)
SELECT D.D4_FILIAL AS "Filial", D.D4_OP AS "OP",
       D.D4_COD AS "Codigo", D.D4_QTDEORI AS "Quantidade"
FROM SD4010 D
WHERE D.D_E_L_E_T_ = ' '
  AND EXISTS (
      SELECT 1 FROM OpsNoPeriodo X
      WHERE X.Filial = D.D4_FILIAL AND X.OP = D.D4_OP
  )
"""

# Query 5: SH6010 com H6_OP vazio + H6_MOTIVO não null (paradas de máquina).
# Semântica original: filtra pelo período das janelas de produção calculadas,
# mas aqui puxamos todas e filtramos em Python (bem menor que apontamentos).
_SQL_PARADAS = """
SELECT TRIM(H.H6_FILIAL) AS "Filial", H.H6_RECURSO AS "Recurso",
       H.H6_PRODUTO AS "Produto",
       H.H6_DATAINI AS "DataIniRaw", H.H6_HORAINI AS "HoraIniRaw",
       H.H6_DATAFIN AS "DataFinRaw", H.H6_HORAFIN AS "HoraFinRaw"
FROM SH6010 H
WHERE H.D_E_L_E_T_ = ' '
  AND TRIM(H.H6_OP) IS NULL
  AND TRIM(H.H6_MOTIVO) IS NOT NULL
"""

# Lookups: tabelas pequenas, puxar inteiras.
_SQL_SG2 = """
SELECT TRIM(G2_FILIAL) AS "Filial", G2_PRODUTO AS "Produto",
       G2_CODIGO AS "Roteiro", G2_OPERAC AS "Operacao",
       G2_DESCRI AS "Descricao", R_E_C_N_O_ AS "Recno"
FROM SG2010 WHERE D_E_L_E_T_ = ' '
"""

_SQL_SH1 = """
SELECT TRIM(H1_FILIAL) AS "Filial", H1_CODIGO AS "Codigo",
       H1_DESCRI AS "Descricao", R_E_C_N_O_ AS "Recno"
FROM SH1010 WHERE D_E_L_E_T_ = ' '
"""

_SQL_SA1 = """
SELECT TRIM(A1_FILIAL) AS "Filial", A1_COD AS "Codigo", A1_LOJA AS "Loja",
       A1_NOME AS "Nome", R_E_C_N_O_ AS "Recno"
FROM SA1010 WHERE D_E_L_E_T_ = ' '
"""


# Ordem das colunas no output final.
COLUNAS_FINAIS = [
    "FILIAL", "OP", "STATUS DA OP", "OPERAÇÃO", "NOME DA OPERAÇÃO",
    "RECURSO", "DESCRIÇÃO DO RECURSO", "H6_RECURSO", "DESCRIÇÃO DO RECURSO APONTADO",
    "ROTEIRO", "OPERADOR", "CLIENTE", "NOME CLIENTE",
    "PRODUTO FINAL", "UNIDADE DE MEDIDA", "FOLHA / BOBINA",
    "DESCRIÇÃO PRODUTO", "LARGURA DO PRODUTO FINAL", "COMPRIMENTO DO PRODUTO FINAL",
    "GRAMATURA TOTAL", "DATA PREVISTA", "DATA/HR INICIO", "DATA/HR FIM",
    "Prod. Real", "Setup Real", "Parada Real", "Tempo Real",
    "Real. Ton/Hora", "VELOCIDADE M/MIN", "QUANTIDADE PREVISTA EM TN",
    "PESO DOS LOTES PRODUZIDOS EM TN", "CONTAGEM DOS LOTES PRODUZIDOS",
    "PESO DOS LOTES CONSUMIDOS EM TN", "CONTAGEM DOS LOTES CONSUMIDOS",
    "TUBETE", "DESCRIÇÃO DO TUBETE",
]


# ============================================================================
# Helpers de tempo
# ============================================================================

def _combine_data_hora(data: pd.Series, hora: pd.Series) -> pd.Series:
    """
    Combina H6_DATAINI (string AAAAMMDD) + H6_HORAINI (string HH:MM ou HH:MM:SS)
    em datetime64. Valores inválidos viram NaT (equivale ao DEFAULT NULL ON
    CONVERSION ERROR do SQL).
    """
    data_s = data.fillna("").astype(str).str.strip()
    hora_s = hora.fillna("").astype(str).str.strip()
    # Hora HH:MM vira HH:MM:00
    hora_s = hora_s.where(hora_s.str.len() != 5, hora_s + ":00")
    combo = data_s + " " + hora_s
    return pd.to_datetime(combo, format="%Y%m%d %H:%M:%S", errors="coerce")


def _combine_data(data: pd.Series) -> pd.Series:
    """Converte H6_DATAINI ou C2_DATPRI (string AAAAMMDD) em datetime64."""
    s = data.fillna("").astype(str).str.strip()
    return pd.to_datetime(s, format="%Y%m%d", errors="coerce")


def _fmt_date(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return ""
    return ts.strftime("%d/%m/%Y")


def _fmt_datetime(ts: pd.Timestamp) -> str:
    if pd.isna(ts):
        return ""
    return ts.strftime("%d/%m/%Y %H:%M")


def _fmt_hhmm(minutos: float) -> str:
    """ "HHH:MM" com no mínimo 2 dígitos de hora (padding com 0)."""
    if pd.isna(minutos) or minutos < 0:
        return ""
    m = int(round(minutos))
    h = m // 60
    mm = m % 60
    if h < 10:
        return f"0{h}:{mm:02d}"
    return f"{h}:{mm:02d}"


def _fmt_num(x, casas: int) -> str:
    """Formato Oracle TM9 com vírgula decimal. Suprime zeros à direita."""
    if pd.isna(x):
        return ""
    s = f"{x:.{casas}f}"
    # Remove zeros à direita e ponto se não sobrar decimal
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s.replace(".", ",")


# ============================================================================
# Função principal
# ============================================================================

def extrair_op_produtivo(
    data_inicio: str, data_fim: str, ctx=None,
) -> pd.DataFrame:
    """
    data_inicio/data_fim em AAAAMMDD. `ctx` opcional pra heartbeat.
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
            log.warning("[OP_PROD DIAG] %s em %.1fs", nome, dt)
        else:
            log.warning("[OP_PROD DIAG] %s em %.1fs (%d linhas)", nome, dt, qtd)

    params = {"data_inicio": data_inicio, "data_fim": data_fim}

    conn = get_oracle_connection()
    try:
        t = time.monotonic()
        df_oa = pd.read_sql(_SQL_ORDENS_APONT, conn, params=params)
        _marco("sql.ordens_apontamentos", t, len(df_oa))
        _bater()

        t = time.monotonic()
        df_ord_todas = pd.read_sql(_SQL_ORDENS_SEM_APONT, conn, params=params)
        _marco("sql.ordens_todas", t, len(df_ord_todas))
        _bater()

        t = time.monotonic()
        df_prod = pd.read_sql(_SQL_PRODUTOS, conn)
        _marco("sql.produtos", t, len(df_prod))
        _bater()

        t = time.monotonic()
        df_emp = pd.read_sql(_SQL_EMPENHOS, conn, params=params)
        _marco("sql.empenhos", t, len(df_emp))
        _bater()

        t = time.monotonic()
        df_par = pd.read_sql(_SQL_PARADAS, conn)
        _marco("sql.paradas", t, len(df_par))
        _bater()

        t = time.monotonic()
        df_sg2 = pd.read_sql(_SQL_SG2, conn)
        _marco("sql.sg2", t, len(df_sg2))

        t = time.monotonic()
        df_sh1 = pd.read_sql(_SQL_SH1, conn)
        _marco("sql.sh1", t, len(df_sh1))

        t = time.monotonic()
        df_sa1 = pd.read_sql(_SQL_SA1, conn)
        _marco("sql.sa1", t, len(df_sa1))
    finally:
        conn.close()
    _bater()

    # Early exit: nenhuma ordem no período
    if df_ord_todas.empty:
        return pd.DataFrame(columns=COLUNAS_FINAIS)

    # ============== Fase 1: processa apontamentos ==============
    t = time.monotonic()
    producao = _agregar_producao(df_oa, df_prod, _bater, _marco)
    _marco("agregar_producao", t, len(producao))
    _bater()

    # ============== Fase 2: resolve produto final por OP ==============
    t = time.monotonic()
    # Base de ordens — 1 linha por OP, sem apontamentos.
    ordens = df_ord_todas.copy()
    ordens["Filial_s"] = ordens["Filial"].astype(str).str.strip()

    # Passa `producao` pra resolver_produto_final: ele precisa do ProdutoApontado
    # mas sem poluir o DataFrame ordens.
    produto_final = _resolver_produto_final(ordens, producao, df_prod)
    _marco("produto_final", t, len(produto_final))
    _bater()

    # ============== Fase 3: consumo + tubetes (SD4) ==============
    t = time.monotonic()
    consumo, tubetes = _calcular_consumo_tubetes(df_emp, df_prod)
    _marco("consumo_tubetes", t, len(consumo))
    _bater()

    # ============== Fase 4: paradas (SH6010 sem OP) ==============
    t = time.monotonic()
    paradas_por_op = _calcular_paradas(df_oa, df_par)
    _marco("paradas", t, len(paradas_por_op))
    _bater()

    # ============== Fase 5: lookups (SG2, SH1, SA1) ==============
    t = time.monotonic()
    lookups = _resolver_lookups(ordens, producao, produto_final, df_sg2, df_sh1, df_sa1)
    _marco("lookups", t)
    _bater()

    # ============== Fase 6: monta output final ==============
    t = time.monotonic()
    df_final = _montar_output(
        ordens, producao, produto_final, consumo, tubetes,
        paradas_por_op, lookups, df_prod,
    )
    _marco("montar_output", t, len(df_final))
    _bater()

    return df_final


# ============================================================================
# Fase 1 — agrega apontamentos por OP (substitui o CTE Producao do SQL)
# ============================================================================

def _agregar_producao(df_oa: pd.DataFrame, df_prod: pd.DataFrame,
                     _bater, _marco) -> pd.DataFrame:
    """
    Pra cada (Filial, OP), devolve:
      - DataInicio/HoraInicio (do apontamento MAIS ANTIGO)
      - DataFim/HoraFim (do apontamento MAIS RECENTE)
      - MinutosReal, MinutosSetup (SUMs com filtro)
      - LotesProduzidos, LotesConsumidos (COUNT DISTINCT)
      - Operacao, Operador, RecursoApontado, ProdutoApontado (do apontamento
        MAIS RECENTE — mesmo critério do ORDER BY MAX(CASE OrdemRecente=1))
      - PesoProduzidoTN (SUM por unidade de medida do Produto)
    """
    if df_oa.empty:
        return pd.DataFrame(columns=[
            "Filial", "OP", "DataInicio", "HoraInicio", "DataFim", "HoraFim",
            "MinutosReal", "MinutosSetup", "MinutosProducao",
            "LotesProduzidos", "LotesConsumidos",
            "Operacao", "Operador", "RecursoApontado", "ProdutoApontado",
            "PesoProduzidoTN",
        ])

    df = df_oa.copy()

    # Monta Inicio e Fim como datetime completo
    df["DataInicio"] = _combine_data(df["H_DataIniRaw"])
    df["DataFim"] = _combine_data(df["H_DataFinRaw"])
    df["HoraInicio_dt"] = _combine_data_hora(df["H_DataIniRaw"], df["H_HoraIniRaw"])
    df["HoraFim_dt"] = _combine_data_hora(df["H_DataFinRaw"], df["H_HoraFinRaw"])
    # Hora como time of day pra output
    df["HoraInicio_str"] = df["H_HoraIniRaw"].fillna("").astype(str).str.strip().str[:5]
    df["HoraFim_str"] = df["H_HoraFinRaw"].fillna("").astype(str).str.strip().str[:5]

    # Intervalo em minutos (só se Fim > Inicio)
    delta = (df["HoraFim_dt"] - df["HoraInicio_dt"]).dt.total_seconds() / 60.0
    df["MinutosInterval"] = np.where(delta > 0, delta, 0.0)
    df["IsSetup"] = df["H_Operacao"].astype(str).str.strip().str.lstrip("0") == "5"
    df["MinutosSetupLinha"] = np.where(df["IsSetup"], df["MinutosInterval"], 0.0)

    # Peso por linha: depende da UM do Produto apontado (com fallback na OP.Produto).
    # Resolve a UM via lookup em df_prod (prefere mesma filial).
    _bater()
    produto_chave = df["H_Produto"].astype(str).str.strip().str.rstrip().replace("", np.nan)
    produto_fallback = df["O_Produto"].astype(str).str.strip().str.rstrip()
    produto_chave = produto_chave.fillna(produto_fallback)
    filial = df["O_Filial"].astype(str).str.strip()

    produto_info = _rank_produto(produto_chave, filial, df_prod)
    df["prod_UM"] = produto_info["UM"].values
    df["prod_Gramatura"] = produto_info["Gramatura"].values
    df["prod_Largura"] = produto_info["Largura"].values
    df["prod_Comprimento"] = produto_info["Comprimento"].values

    qtd = pd.to_numeric(df["H_Quantidade"], errors="coerce").fillna(0.0)
    um = df["prod_UM"].fillna("")
    peso = np.where(
        um == "KG", qtd / 1000.0,
        np.where(
            um == "FL",
            df["prod_Gramatura"].fillna(0) * df["prod_Largura"].fillna(0) * df["prod_Comprimento"].fillna(0) * qtd / 1_000_000_000_000,
            np.where(um == "TN", qtd, 0.0),
        ),
    )
    df["PesoLinhaTN"] = peso
    _bater()

    # Agrupa por (Filial, OP). Faz várias operações em passagens separadas pra
    # evitar perder tempo em multi-agg custoso.
    key = ["O_Filial", "O_OP"]

    # Agregações numéricas básicas
    agg_num = df.groupby(key, sort=False).agg(
        MinutosReal=("MinutosInterval", "sum"),
        MinutosSetup=("MinutosSetupLinha", "sum"),
        LotesProduzidos=("H_LoteProduzido", lambda s: s.dropna().astype(str).str.strip().replace("", np.nan).dropna().nunique()),
        LotesConsumidos=("H_LoteConsumido", lambda s: s.dropna().astype(str).str.strip().replace("", np.nan).dropna().nunique()),
        PesoProduzidoTN=("PesoLinhaTN", "sum"),
    ).reset_index()

    # Primeira linha ordenada por DataInicio/HoraInicio asc, Recno asc → DataInicio/HoraInicio da OP
    df_s_ini = df.sort_values(
        ["O_Filial", "O_OP", "DataInicio", "HoraInicio_dt", "H_Recno"],
        na_position="last",
    )
    primeiros = df_s_ini.groupby(key, sort=False).first().reset_index()
    primeiros = primeiros[["O_Filial", "O_OP", "DataInicio", "HoraInicio_str"]].rename(
        columns={"DataInicio": "DataInicioOP", "HoraInicio_str": "HoraInicio"},
    )

    # Última linha ordenada por DataFim desc, HoraFim desc, Recno desc → DataFim/HoraFim da OP
    df_s_fim = df.sort_values(
        ["O_Filial", "O_OP", "DataFim", "HoraFim_dt", "H_Recno"],
        ascending=[True, True, False, False, False],
        na_position="last",
    )
    ultimos_fim = df_s_fim.groupby(key, sort=False).first().reset_index()
    ultimos_fim = ultimos_fim[["O_Filial", "O_OP", "DataFim", "HoraFim_str"]].rename(
        columns={"DataFim": "DataFimOP", "HoraFim_str": "HoraFim"},
    )

    # Último apontamento (OrdemRecente=1): usa DataFim desc, HoraFim desc, Recno desc.
    # Se DataFim for null, o original cai pra DataInicio/HoraInicio. Pandas sort_values
    # com NaT no DataFim e ordem desc já joga as DataFim-null pro fim; precisamos
    # pegar as ultimas por critério:
    #   COALESCE(DataFim, DataInicio) DESC NULLS LAST,
    #   CASE WHEN DataFim IS NOT NULL THEN HoraFim ELSE HoraInicio END DESC NULLS LAST,
    #   Recno DESC
    df["RecenteDataChave"] = df["DataFim"].fillna(df["DataInicio"])
    df["RecenteHoraChave"] = np.where(
        df["DataFim"].notna(), df["HoraFim_dt"], df["HoraInicio_dt"],
    )
    # Transforma o np.where (object array) de volta em datetime
    df["RecenteHoraChave"] = pd.to_datetime(df["RecenteHoraChave"])
    df_s_recente = df.sort_values(
        ["O_Filial", "O_OP", "RecenteDataChave", "RecenteHoraChave", "H_Recno"],
        ascending=[True, True, False, False, False],
        na_position="last",
    )
    recentes = df_s_recente.groupby(key, sort=False).first().reset_index()
    recentes = recentes[["O_Filial", "O_OP",
                         "H_Operacao", "H_Operador", "H_RecursoApontado", "H_Produto"]].rename(
        columns={
            "H_Operacao": "Operacao",
            "H_Operador": "Operador",
            "H_RecursoApontado": "RecursoApontado",
            "H_Produto": "ProdutoApontado",
        },
    )

    # Junta tudo
    prod = agg_num.merge(primeiros, on=key).merge(ultimos_fim, on=key).merge(recentes, on=key)
    prod = prod.rename(columns={"O_Filial": "Filial", "O_OP": "OP",
                                "DataInicioOP": "DataInicio", "DataFimOP": "DataFim"})

    # MinutosProducao = (DataFim - DataInicio) * 1440 + (HoraFim mod dia - HoraInicio mod dia) * 1440
    # Usa o datetime completo (data+hora) pra calcular
    # Reusa HoraInicio_dt e HoraFim_dt dos primeiros/ultimos
    df_s_ini_g = df_s_ini.groupby(key, sort=False).first().reset_index()
    df_s_fim_g = df_s_fim.groupby(key, sort=False).first().reset_index()
    ini_dt = df_s_ini_g["HoraInicio_dt"]
    fim_dt = df_s_fim_g["HoraFim_dt"]
    minutos_prod = (fim_dt - ini_dt).dt.total_seconds() / 60.0
    prod_min_df = pd.DataFrame({
        "Filial": df_s_ini_g["O_Filial"].values,
        "OP": df_s_ini_g["O_OP"].values,
        "MinutosProducao": minutos_prod.values,
    })
    prod = prod.merge(prod_min_df, on=["Filial", "OP"], how="left")

    return prod


# ============================================================================
# Helper — ranking de Produto (com preferência filial-específica)
# ============================================================================

def _rank_produto(codigos: pd.Series, filiais: pd.Series,
                  df_prod: pd.DataFrame) -> pd.DataFrame:
    """
    Pra cada (codigo, filial), devolve a melhor linha do SB1010:
      - Preferência: Filial = TRIM(filial), depois Filial IS NULL
      - Tiebreak: Recno DESC
    Devolve DataFrame com UM, Gramatura, Largura, Comprimento, Descricao,
    Codigo — índice alinhado ao input (mesmo tamanho, mesma ordem).
    """
    n = len(codigos)
    if n == 0:
        return pd.DataFrame(columns=["UM", "Gramatura", "Largura", "Comprimento",
                                      "Descricao", "Codigo"])

    # Normaliza filial dos produtos pra string vazia quando null (pra bater com filial)
    prod = df_prod.copy()
    prod["Filial_s"] = prod["Filial"].fillna("").astype(str).str.strip()
    prod["Codigo_s"] = prod["Codigo"].astype(str).str.rstrip()

    # Ordena produtos pra priorizar genérico (Filial="") por último quando empatar
    # Mas o rank é FEITO POR LINHA DE ENTRADA considerando a filial dela.
    # Estratégia: fazer 2 merges — 1 pra filial-específica, 1 pra genérica.
    input_df = pd.DataFrame({
        "cod": codigos.astype(str).str.rstrip().values,
        "fil": filiais.astype(str).str.strip().values,
    })

    # Melhor por filial-específica
    prod_fil = prod[prod["Filial_s"] != ""].sort_values("Recno", ascending=False)
    prod_fil = prod_fil.drop_duplicates(subset=["Codigo_s", "Filial_s"], keep="first")

    # Melhor genérico
    prod_gen = prod[prod["Filial_s"] == ""].sort_values("Recno", ascending=False)
    prod_gen = prod_gen.drop_duplicates(subset=["Codigo_s"], keep="first")

    # Merge filial-específica
    cols_out = ["UM", "Gramatura", "Largura", "Comprimento", "Descricao", "Codigo"]
    m1 = input_df.merge(
        prod_fil[["Codigo_s", "Filial_s"] + cols_out],
        left_on=["cod", "fil"], right_on=["Codigo_s", "Filial_s"], how="left",
    )
    # Merge genérico — só pra linhas que o primeiro não resolveu
    m2 = input_df.merge(
        prod_gen[["Codigo_s"] + cols_out],
        left_on="cod", right_on="Codigo_s", how="left",
        suffixes=("", "_gen"),
    )

    out = pd.DataFrame(index=range(n))
    for c in cols_out:
        out[c] = m1[c].values
        mask_null = out[c].isna()
        out.loc[mask_null, c] = m2[c].values[mask_null]
    return out


# ============================================================================
# Fase 2 — resolve Produto final por OP
# ============================================================================

def _resolver_produto_final(ordens: pd.DataFrame, producao: pd.DataFrame,
                           df_prod: pd.DataFrame) -> pd.DataFrame:
    """
    Pra cada ordem, produto final = ProdutoApontado (da Producao, se existir)
    senão O.Produto. Resolve UM/Descricao/Dimensões via _rank_produto.
    """
    tmp = ordens[["Filial", "OP", "Filial_s", "Produto"]].merge(
        producao[["Filial", "OP", "ProdutoApontado"]],
        on=["Filial", "OP"], how="left",
    )
    cod_apontado = tmp["ProdutoApontado"].astype(str).str.strip().str.rstrip()
    cod_apontado = cod_apontado.replace({"": np.nan, "nan": np.nan, "None": np.nan})
    cod_ordem = tmp["Produto"].astype(str).str.rstrip()
    chave = cod_apontado.fillna(cod_ordem)
    filial = tmp["Filial_s"]

    rank = _rank_produto(chave, filial, df_prod)
    result = tmp[["Filial", "OP"]].copy()
    for c in ["UM", "Gramatura", "Largura", "Comprimento", "Descricao", "Codigo"]:
        result[f"PF_{c}"] = rank[c].values
    return result


# ============================================================================
# Fase 3 — consumo + tubetes
# ============================================================================

def _calcular_consumo_tubetes(df_emp: pd.DataFrame,
                              df_prod: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Pra cada empenho, resolve produto; calcula PesoTN; agrega consumo total por
    OP e tubetes (UM = 'PC').
    """
    if df_emp.empty:
        return (pd.DataFrame(columns=["Filial", "OP", "PesoConsumidoTN"]),
                pd.DataFrame(columns=["Filial", "OP", "TUBETE", "DESCRIÇÃO DO TUBETE"]))

    df = df_emp.copy()
    df["cod"] = df["Codigo"].astype(str).str.rstrip()
    df["fil"] = df["Filial"].astype(str).str.strip()

    rank = _rank_produto(df["cod"], df["fil"], df_prod)
    df["UM"] = rank["UM"].values
    df["Gramatura"] = rank["Gramatura"].values
    df["Largura"] = rank["Largura"].values
    df["Comprimento"] = rank["Comprimento"].values
    df["Descricao"] = rank["Descricao"].values

    qtd = pd.to_numeric(df["Quantidade"], errors="coerce").fillna(0.0)
    um = df["UM"].fillna("")
    peso = np.where(
        um == "KG", qtd / 1000.0,
        np.where(
            um == "FL",
            df["Gramatura"].fillna(0) * df["Largura"].fillna(0) * df["Comprimento"].fillna(0) * qtd / 1_000_000_000_000,
            np.where(um == "TN", qtd, np.nan),
        ),
    )
    df["PesoTN"] = peso

    # Consumo
    consumo = df.groupby(["Filial", "OP"], as_index=False, sort=False)["PesoTN"].sum().rename(
        columns={"PesoTN": "PesoConsumidoTN"},
    )

    # Tubetes: UM = 'PC'
    df_t = df[df["UM"] == "PC"].copy()
    if df_t.empty:
        tubetes = pd.DataFrame(columns=["Filial", "OP", "TUBETE", "DESCRIÇÃO DO TUBETE"])
    else:
        df_t["cod_distinct"] = df_t["cod"].fillna("")
        df_t["desc_distinct"] = df_t["Descricao"].fillna(df_t["cod_distinct"])
        df_t = df_t.drop_duplicates(subset=["Filial", "OP", "cod_distinct", "desc_distinct"])
        df_t = df_t.sort_values(["Filial", "OP", "cod_distinct", "desc_distinct"])
        tubetes = df_t.groupby(["Filial", "OP"], as_index=False, sort=False).agg(
            TUBETE=("cod_distinct", lambda s: " | ".join(s)),
            **{"DESCRIÇÃO DO TUBETE": ("desc_distinct", lambda s: " | ".join(s))},
        )

    return consumo, tubetes


# ============================================================================
# Fase 4 — paradas de máquina
# ============================================================================

def _calcular_paradas(df_oa: pd.DataFrame, df_par: pd.DataFrame) -> pd.DataFrame:
    """
    Pra cada OP, calcula MinutosParada = soma das interseções (merge-overlap)
    entre janelas de produção da OP e paradas da mesma máquina.
    """
    if df_oa.empty or df_par.empty:
        return pd.DataFrame(columns=["Filial", "OP", "MinutosParada"])

    # Monta janelas de produção (1 por apontamento válido)
    df = df_oa.copy()
    df["Inicio"] = _combine_data_hora(df["H_DataIniRaw"], df["H_HoraIniRaw"])
    df["Fim"] = _combine_data_hora(df["H_DataFinRaw"], df["H_HoraFinRaw"])
    df["RecursoApontado_s"] = df["H_RecursoApontado"].astype(str).str.strip()
    df["Operador_s"] = df["H_Operador"].astype(str).str.strip()
    df["Filial_s"] = df["O_Filial"].astype(str).str.strip()
    df["Produto_s"] = df["H_Produto"].astype(str).str.rstrip()

    j = df[
        (df["Fim"] > df["Inicio"])
        & (df["Operador_s"] != "")
        & (df["RecursoApontado_s"] != "")
    ][["O_Filial", "O_OP", "Filial_s", "RecursoApontado_s", "Produto_s", "Inicio", "Fim"]]
    j = j.drop_duplicates()
    j = j.rename(columns={"O_Filial": "Filial", "O_OP": "OP",
                          "RecursoApontado_s": "Recurso", "Produto_s": "Produto"})

    if j.empty:
        return pd.DataFrame(columns=["Filial", "OP", "MinutosParada"])

    # Monta paradas: 1 linha por parada, com Inicio/Fim como datetime
    p = df_par.copy()
    p["Inicio"] = _combine_data_hora(p["DataIniRaw"], p["HoraIniRaw"])
    p["Fim"] = _combine_data_hora(p["DataFinRaw"], p["HoraFinRaw"])
    p["Produto_s"] = p["Produto"].astype(str).str.rstrip()
    p["Recurso_s"] = p["Recurso"].astype(str).str.strip()
    p["Filial_s"] = p["Filial"].astype(str).str.strip()
    p = p[p["Fim"] > p["Inicio"]][["Filial_s", "Recurso_s", "Produto_s", "Inicio", "Fim"]]
    p = p.rename(columns={"Filial_s": "Filial", "Recurso_s": "Recurso", "Produto_s": "Produto"})

    if p.empty:
        return pd.DataFrame(columns=["Filial", "OP", "MinutosParada"])

    # Interseção: join janela × parada pela mesma (Filial, Recurso), filtra
    # produto igual OU produto da parada vazio, e janelas que sobrepõem.
    jm = j.merge(p, on=["Filial", "Recurso"], suffixes=("_j", "_p"))
    jm = jm[(jm["Produto_p"] == "") | (jm["Produto_p"] == jm["Produto_j"])]
    jm = jm[(jm["Inicio_p"] < jm["Fim_j"]) & (jm["Fim_p"] > jm["Inicio_j"])]
    if jm.empty:
        return pd.DataFrame(columns=["Filial", "OP", "MinutosParada"])

    jm["IntInicio"] = np.maximum(jm["Inicio_j"], jm["Inicio_p"])
    jm["IntFim"] = np.minimum(jm["Fim_j"], jm["Fim_p"])
    trechos = jm[["Filial", "OP", "IntInicio", "IntFim"]].drop_duplicates()

    # Merge-overlap por (Filial, OP): soma minutos únicos sem dupla contagem.
    trechos = trechos.sort_values(["Filial", "OP", "IntInicio", "IntFim"])

    minutos_por_op: dict[tuple, float] = {}
    chave_atual = (None, None)
    fim_corrente = None
    for row in trechos.itertuples(index=False):
        chave = (row.Filial, row.OP)
        if chave != chave_atual:
            chave_atual = chave
            fim_corrente = None
            minutos_por_op.setdefault(chave, 0.0)
        ini_eff = row.IntInicio if fim_corrente is None else max(row.IntInicio, fim_corrente)
        if row.IntFim > ini_eff:
            minutos_por_op[chave] += (row.IntFim - ini_eff).total_seconds() / 60.0
            if fim_corrente is None or row.IntFim > fim_corrente:
                fim_corrente = row.IntFim

    out = pd.DataFrame(
        [(f, o, m) for (f, o), m in minutos_por_op.items()],
        columns=["Filial", "OP", "MinutosParada"],
    )
    return out


# ============================================================================
# Fase 5 — lookups (SG2010, SH1010 2x, SA1010)
# ============================================================================

def _best_lookup(chaves: pd.DataFrame, lookup_df: pd.DataFrame,
                 chaves_cols: list[str], filial_col_input: str,
                 return_col: str) -> pd.Series:
    """
    Pra cada linha de `chaves`, acha a melhor linha de `lookup_df` com as
    mesmas `chaves_cols`, preferindo filial-específica (Filial = filial da
    chave), depois genérica (Filial vazia), tiebreak por Recno DESC.

    Devolve Series alinhada ao input com o valor da coluna `return_col`.
    """
    n = len(chaves)
    if n == 0 or lookup_df.empty:
        return pd.Series([None] * n)

    lk = lookup_df.copy()
    lk["Filial_s"] = lk["Filial"].fillna("").astype(str).str.strip()

    # Prepara chaves normalizadas
    input_norm = pd.DataFrame(index=range(n))
    for c in chaves_cols:
        input_norm[c] = chaves[c].astype(str).str.strip().values
    input_norm["fil"] = chaves[filial_col_input].astype(str).str.strip().values

    # Melhor por filial-específica
    lk_fil = lk[lk["Filial_s"] != ""].sort_values("Recno", ascending=False)
    lk_fil = lk_fil.drop_duplicates(subset=chaves_cols + ["Filial_s"], keep="first")
    m1 = input_norm.merge(
        lk_fil[chaves_cols + ["Filial_s", return_col]],
        left_on=chaves_cols + ["fil"], right_on=chaves_cols + ["Filial_s"],
        how="left",
    )

    # Melhor genérico
    lk_gen = lk[lk["Filial_s"] == ""].sort_values("Recno", ascending=False)
    lk_gen = lk_gen.drop_duplicates(subset=chaves_cols, keep="first")
    m2 = input_norm.merge(
        lk_gen[chaves_cols + [return_col]],
        on=chaves_cols, how="left", suffixes=("", "_gen"),
    )

    out = m1[return_col].copy()
    mask_null = out.isna()
    out[mask_null] = m2[return_col].values[mask_null]
    return out


def _resolver_lookups(ordens: pd.DataFrame, producao: pd.DataFrame,
                     produto_final: pd.DataFrame,
                     df_sg2: pd.DataFrame, df_sh1: pd.DataFrame,
                     df_sa1: pd.DataFrame) -> dict:
    """
    Resolve 4 lookups por linha de ordem:
      - Nome da operação (SG2010): chave = (Produto final, Roteiro, Operacao recente)
      - Descrição do recurso (SH1010): chave = Recurso
      - Descrição do recurso apontado (SH1010): chave = RecursoApontado recente
      - Nome do cliente (SA1010): chave = (Cliente, LojaCliente)
    """
    # Chave do SG2 precisa de OPERACAO (vem de producao) + PRODUTO FINAL (vem de produto_final)
    base = ordens[["Filial", "OP", "Filial_s", "Roteiro", "Recurso",
                   "Cliente", "LojaCliente"]].merge(
        producao[["Filial", "OP", "Operacao", "RecursoApontado"]], on=["Filial", "OP"], how="left",
    ).merge(
        produto_final[["Filial", "OP", "PF_Codigo"]], on=["Filial", "OP"], how="left",
    )
    base["Operacao_s"] = base["Operacao"].fillna("").astype(str).str.strip()
    base["Roteiro_s"] = base["Roteiro"].fillna("").astype(str).str.strip()
    base["ProdutoFinal_s"] = base["PF_Codigo"].fillna("").astype(str).str.strip()
    base["Recurso_s"] = base["Recurso"].fillna("").astype(str).str.strip()
    base["RecursoApontado_s"] = base["RecursoApontado"].fillna("").astype(str).str.strip()
    base["Cliente_s"] = base["Cliente"].fillna("").astype(str).str.strip()
    base["LojaCliente_s"] = base["LojaCliente"].fillna("").astype(str).str.strip()

    # SG2010
    sg2 = df_sg2.copy()
    sg2["Produto_s"] = sg2["Produto"].astype(str).str.strip()
    sg2["Roteiro_s"] = sg2["Roteiro"].astype(str).str.strip()
    sg2["Operacao_s"] = sg2["Operacao"].astype(str).str.strip()
    sg2_input = pd.DataFrame({
        "Produto_s": base["ProdutoFinal_s"].values,
        "Roteiro_s": base["Roteiro_s"].values,
        "Operacao_s": base["Operacao_s"].values,
        "fil_input": base["Filial_s"].values,
    })
    g_desc = _best_lookup(sg2_input, sg2.rename(columns={"Descricao": "G_DESC"}),
                          chaves_cols=["Produto_s", "Roteiro_s", "Operacao_s"],
                          filial_col_input="fil_input", return_col="G_DESC")

    # SH1010 x2
    sh1 = df_sh1.copy()
    sh1["Codigo_s"] = sh1["Codigo"].astype(str).str.strip()

    sh1_input_r = pd.DataFrame({
        "Codigo_s": base["Recurso_s"].values,
        "fil_input": base["Filial_s"].values,
    })
    r_desc = _best_lookup(sh1_input_r, sh1.rename(columns={"Descricao": "R_DESC"}),
                          chaves_cols=["Codigo_s"],
                          filial_col_input="fil_input", return_col="R_DESC")
    # Linhas com Recurso vazio devem ficar sem descrição
    r_desc = r_desc.where(base["Recurso_s"] != "", None)

    sh1_input_ra = pd.DataFrame({
        "Codigo_s": base["RecursoApontado_s"].values,
        "fil_input": base["Filial_s"].values,
    })
    ra_desc = _best_lookup(sh1_input_ra, sh1.rename(columns={"Descricao": "RA_DESC"}),
                           chaves_cols=["Codigo_s"],
                           filial_col_input="fil_input", return_col="RA_DESC")
    ra_desc = ra_desc.where(base["RecursoApontado_s"] != "", None)

    # SA1010
    sa1 = df_sa1.copy()
    sa1["Codigo_s"] = sa1["Codigo"].astype(str).str.strip()
    sa1["Loja_s"] = sa1["Loja"].astype(str).str.strip()
    sa1_input = pd.DataFrame({
        "Codigo_s": base["Cliente_s"].values,
        "Loja_s": base["LojaCliente_s"].values,
        "fil_input": base["Filial_s"].values,
    })
    c_nome = _best_lookup(sa1_input, sa1.rename(columns={"Nome": "C_NOME"}),
                          chaves_cols=["Codigo_s", "Loja_s"],
                          filial_col_input="fil_input", return_col="C_NOME")
    c_nome = c_nome.where(base["Cliente_s"] != "", None)

    # Devolve dict com Series alinhadas por (Filial, OP) via índice posicional
    return {
        "NomeOperacao": g_desc.reset_index(drop=True),
        "RecursoDesc": r_desc.reset_index(drop=True),
        "RecursoApontadoDesc": ra_desc.reset_index(drop=True),
        "ClienteNome": c_nome.reset_index(drop=True),
        "FOP_pair": base[["Filial", "OP"]].reset_index(drop=True),
    }


# ============================================================================
# Fase 6 — monta output final (formatação)
# ============================================================================

def _montar_output(ordens, producao, produto_final, consumo, tubetes,
                   paradas_por_op, lookups, df_prod) -> pd.DataFrame:
    df = ordens.copy()

    # Junta producao
    df = df.merge(producao, on=["Filial", "OP"], how="left")

    # Junta produto_final
    df = df.merge(produto_final, on=["Filial", "OP"], how="left")

    # Junta consumo
    df = df.merge(consumo, on=["Filial", "OP"], how="left")

    # Junta tubetes
    df = df.merge(tubetes, on=["Filial", "OP"], how="left")

    # Junta paradas
    df = df.merge(paradas_por_op, on=["Filial", "OP"], how="left")

    # Junta lookups via par (Filial, OP) do próprio base
    lk_df = lookups["FOP_pair"].copy()
    lk_df["NomeOperacao"] = lookups["NomeOperacao"].values
    lk_df["RecursoDesc"] = lookups["RecursoDesc"].values
    lk_df["RecursoApontadoDesc"] = lookups["RecursoApontadoDesc"].values
    lk_df["ClienteNome"] = lookups["ClienteNome"].values
    df = df.merge(lk_df, on=["Filial", "OP"], how="left")

    # Normaliza MinutosParada default 0
    df["MinutosParada"] = df["MinutosParada"].fillna(0.0)
    df["MinutosProducaoLiquida"] = (
        df["MinutosReal"].fillna(0) - df["MinutosSetup"].fillna(0) - df["MinutosParada"]
    )

    # Status da OP
    def _status(r):
        if pd.isna(r["DataInicio"]):
            return "NÃO INICIADA"
        if pd.isna(r["DataFim"]):
            return "EM ANDAMENTO"
        return "FINALIZADA"
    df["STATUS DA OP"] = df.apply(_status, axis=1)

    # PesoProduzidoTN zerado quando OP sem apontamento
    df["TemApontamento"] = df["DataInicio"].notna() | df["DataFim"].notna() | df["PesoProduzidoTN"].notna()
    df["PesoProduzidoTN"] = np.where(df["TemApontamento"], df["PesoProduzidoTN"].fillna(0), 0)
    df["LotesProduzidos"] = df["LotesProduzidos"].fillna(0).astype(int)
    df["LotesConsumidos"] = df["LotesConsumidos"].fillna(0).astype(int)
    df["PesoConsumidoTN"] = df["PesoConsumidoTN"].fillna(0)

    # Data prevista: converte AAAAMMDD → DD/MM/YYYY
    dt_prev = _combine_data(df["DataPrevistaRaw"])
    df["DATA PREVISTA"] = dt_prev.apply(_fmt_date)

    # Data/Hr Início/Fim
    hora_ini_s = df["HoraInicio"].fillna("").astype(str).str[:5]
    hora_fim_s = df["HoraFim"].fillna("").astype(str).str[:5]
    def _dh(d, h):
        if pd.isna(d):
            return ""
        s = d.strftime("%d/%m/%Y")
        return s + (f" {h}" if h and len(h) == 5 else "")
    df["DATA/HR INICIO"] = [_dh(d, h) for d, h in zip(df["DataInicio"], hora_ini_s)]
    df["DATA/HR FIM"] = [_dh(d, h) for d, h in zip(df["DataFim"], hora_fim_s)]

    # Tempos em HHH:MM
    df["Prod. Real"] = df["MinutosProducaoLiquida"].apply(_fmt_hhmm)
    df["Setup Real"] = df["MinutosSetup"].fillna(0).apply(_fmt_hhmm)
    df["Parada Real"] = df["MinutosParada"].apply(_fmt_hhmm)
    df["Tempo Real"] = df["MinutosReal"].fillna(0).apply(_fmt_hhmm)

    # Real. Ton/Hora
    with np.errstate(divide="ignore", invalid="ignore"):
        th = np.where(
            df["MinutosReal"].fillna(0) > 0,
            np.round(df["PesoProduzidoTN"] * 60 / df["MinutosReal"].replace(0, np.nan), 3),
            np.nan,
        )
    df["Real. Ton/Hora"] = pd.Series(th).apply(lambda x: _fmt_num(x, 3))

    # Velocidade m/min
    with np.errstate(divide="ignore", invalid="ignore"):
        larg = pd.to_numeric(df["PF_Largura"], errors="coerce").fillna(0)
        gram = pd.to_numeric(df["PF_Gramatura"], errors="coerce").fillna(0)
        mp = df["MinutosProducao"].fillna(0)
        vel = np.where(
            (larg > 0) & (gram > 0) & (mp > 0),
            np.round((df["PesoProduzidoTN"] * 1000) / ((larg / 1000) * (gram / 1000) * mp.replace(0, np.nan)), 4),
            np.nan,
        )
    df["VELOCIDADE M/MIN"] = pd.Series(vel).apply(lambda x: _fmt_num(x, 4))

    # Quantidade prevista em TN
    um = df["PF_UM"].fillna("")
    qt_prev = pd.to_numeric(df["QuantidadePrevista"], errors="coerce").fillna(0)
    gram_v = pd.to_numeric(df["PF_Gramatura"], errors="coerce").fillna(0)
    larg_v = pd.to_numeric(df["PF_Largura"], errors="coerce").fillna(0)
    comp_v = pd.to_numeric(df["PF_Comprimento"], errors="coerce").fillna(0)
    qprev = np.where(
        um == "KG", qt_prev / 1000.0,
        np.where(
            um == "FL", gram_v * larg_v * comp_v * qt_prev / 1_000_000_000_000,
            np.where(um == "TN", qt_prev, np.nan),
        ),
    )
    df["QUANTIDADE PREVISTA EM TN"] = pd.Series(qprev).apply(lambda x: _fmt_num(x, 6))

    # Peso dos lotes produzidos em TN
    df["PESO DOS LOTES PRODUZIDOS EM TN"] = df["PesoProduzidoTN"].apply(lambda x: _fmt_num(x, 6))
    df["CONTAGEM DOS LOTES PRODUZIDOS"] = df["LotesProduzidos"]

    # Peso dos lotes consumidos em TN
    df["PESO DOS LOTES CONSUMIDOS EM TN"] = df["PesoConsumidoTN"].apply(lambda x: _fmt_num(x, 6))
    df["CONTAGEM DOS LOTES CONSUMIDOS"] = df["LotesConsumidos"]

    # Produto final info
    df["PRODUTO FINAL"] = df["ProdutoApontado"].fillna("").astype(str).str.rstrip()
    df["UNIDADE DE MEDIDA"] = df["PF_UM"]
    df["FOLHA / BOBINA"] = np.where(df["PF_UM"] == "FL", "FOLHA", "BOBINA")
    df["DESCRIÇÃO PRODUTO"] = df["PF_Descricao"]
    df["LARGURA DO PRODUTO FINAL"] = df["PF_Largura"]
    df["COMPRIMENTO DO PRODUTO FINAL"] = np.where(
        df["PF_UM"] == "FL", df["PF_Comprimento"], np.nan,
    )
    df["GRAMATURA TOTAL"] = df["PF_Gramatura"]

    # Rename base
    df["FILIAL"] = df["Filial"].astype(str).str.rstrip()
    df["OP"] = df["OP"].astype(str).str.rstrip()
    df["OPERAÇÃO"] = df["Operacao"].fillna("").astype(str).str.rstrip()
    df["NOME DA OPERAÇÃO"] = df["NomeOperacao"].fillna("").astype(str).str.rstrip()
    df["RECURSO"] = df["Recurso"].astype(str).str.rstrip()
    df["DESCRIÇÃO DO RECURSO"] = df["RecursoDesc"].fillna("").astype(str).str.rstrip()
    df["H6_RECURSO"] = df["RecursoApontado"].fillna("").astype(str).str.rstrip()
    df["DESCRIÇÃO DO RECURSO APONTADO"] = df["RecursoApontadoDesc"].fillna("").astype(str).str.rstrip()
    df["ROTEIRO"] = df["Roteiro"].astype(str).str.rstrip()
    df["OPERADOR"] = df["Operador"].fillna("").astype(str).str.rstrip()
    df["CLIENTE"] = df["Cliente"].astype(str).str.rstrip()
    df["NOME CLIENTE"] = df["ClienteNome"].fillna("").astype(str).str.rstrip()

    df["TUBETE"] = df["TUBETE"].fillna("")
    df["DESCRIÇÃO DO TUBETE"] = df["DESCRIÇÃO DO TUBETE"].fillna("")

    # Seleciona e ordena colunas finais, ordena por Filial, OP
    df_out = df[COLUNAS_FINAIS].sort_values(["FILIAL", "OP"]).reset_index(drop=True)
    return df_out
