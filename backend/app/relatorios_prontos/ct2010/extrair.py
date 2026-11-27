"""
Extração CT2010 com rastreamento de NF.

Portado do desktop. Única mudança: import de conexão Oracle vem de
app.oracle em vez do módulo raiz.

Joins:
  - CV3 (rastreamento contábil) → dá o tipo de origem (SF1/SD1/SF2/SD2)
  - SD1/SF1 (entrada via item/cabeçalho)
  - SD2/SF2 (saída via item/cabeçalho)
  - SA1/SA2 para nome e razão social do cliente/fornecedor

Tudo em LEFT JOIN para NÃO perder lançamentos sem NF (financeiros, ajustes,
provisões). Esses saem no CSV com as colunas de NF em branco.
"""
import logging
import time

import pandas as pd

from app.oracle import get_oracle_connection

log = logging.getLogger(__name__)


# Tamanho do batch de fetch. 5000 linhas por `fetchmany` dá um bom
# equilíbrio: cada batch volta em segundos (mantém o heartbeat vivo) e
# o overhead de chamada python→driver é diluído o suficiente pra não
# dominar o tempo total.
_FETCH_BATCH = 5_000


def extrair_ct2010(data_inicio: str, data_fim: str, ctx=None) -> pd.DataFrame:
    """
    data_inicio e data_fim no formato AAAAMMDD.

    `ctx` é opcional pra manter compat com usos síncronos: quando passado
    (vindo do runner de job), chamamos `ctx.heartbeat()` entre cada batch
    do `fetchmany`. Em bases grandes (CT2010 do ano inteiro) o Oracle pode
    demorar minutos só pra consolidar os JOINs e começar a devolver linhas,
    e o `pd.read_sql()` monolítico esconde esse tempo numa única chamada
    bloqueante — o watchdog marca zumbi mesmo com o worker vivo.

    Com fetchmany manual: o cursor abre, o Oracle começa a streamar, e
    batemos heartbeat entre cada 5k linhas vindas.
    """
    query = """
        SELECT
            CT2.R_E_C_N_O_ AS CT2_RECNO,
            CT2.CT2_FILIAL, CT2.CT2_DATA, CT2.CT2_LOTE, CT2.CT2_DC,
            CT2.CT2_DEBITO, CT2.CT2_CREDIT, CT2.CT2_VALOR,
            CT2.CT2_HIST, CT2.CT2_CCD, CT2.CT2_CCC, CT2.CT2_DOC,
            CT2.CT2_ITEMD, CT2.CT2_ITEMC, CT2.CT2_CLVLDB, CT2.CT2_CLVLCR,
            CT2.CT2_ORIGEM, CT2.CT2_LINHA,
            CASE
                WHEN CV3.CV3_TABORI IN ('SF1', 'SD1') THEN 'ENTRADA'
                WHEN CV3.CV3_TABORI IN ('SF2', 'SD2') THEN 'SAIDA'
                ELSE NULL
            END AS TIPO_OPERACAO,
            COALESCE(SF1_ITEM.F1_DOC, SF1_CAB.F1_DOC,
                     SF2_ITEM.F2_DOC, SF2_CAB.F2_DOC)         AS NUMERO_NF,
            COALESCE(SF1_ITEM.F1_SERIE, SF1_CAB.F1_SERIE,
                     SF2_ITEM.F2_SERIE, SF2_CAB.F2_SERIE)     AS SERIE_NF,
            COALESCE(SF1_ITEM.F1_FORNECE, SF1_CAB.F1_FORNECE,
                     SF2_ITEM.F2_CLIENTE, SF2_CAB.F2_CLIENTE) AS CLI_FOR,
            COALESCE(SF1_ITEM.F1_LOJA, SF1_CAB.F1_LOJA,
                     SF2_ITEM.F2_LOJA, SF2_CAB.F2_LOJA)       AS LOJA,
            COALESCE(SA2.A2_NREDUZ, SA1.A1_NREDUZ) AS NOME_CLIFOR,
            COALESCE(SA2.A2_NOME,   SA1.A1_NOME)   AS RAZAO_SOCIAL
        FROM CT2010 CT2
            LEFT JOIN CV3010 CV3
                ON CV3.CV3_FILIAL = CT2.CT2_FILIAL
                AND TO_NUMBER(TRIM(CV3.CV3_RECDES) DEFAULT 0 ON CONVERSION ERROR) = CT2.R_E_C_N_O_
                AND CV3.D_E_L_E_T_ = ' '
            LEFT JOIN SD1010 SD1
                ON CV3.CV3_TABORI = 'SD1'
                AND TO_NUMBER(TRIM(CV3.CV3_RECORI) DEFAULT 0 ON CONVERSION ERROR) = SD1.R_E_C_N_O_
                AND SD1.D_E_L_E_T_ = ' '
            LEFT JOIN SF1010 SF1_ITEM
                ON SF1_ITEM.F1_FILIAL  = SD1.D1_FILIAL
                AND SF1_ITEM.F1_DOC     = SD1.D1_DOC
                AND SF1_ITEM.F1_SERIE   = SD1.D1_SERIE
                AND SF1_ITEM.F1_FORNECE = SD1.D1_FORNECE
                AND SF1_ITEM.F1_LOJA    = SD1.D1_LOJA
                AND SF1_ITEM.D_E_L_E_T_ = ' '
            LEFT JOIN SF1010 SF1_CAB
                ON CV3.CV3_TABORI = 'SF1'
                AND TO_NUMBER(TRIM(CV3.CV3_RECORI) DEFAULT 0 ON CONVERSION ERROR) = SF1_CAB.R_E_C_N_O_
                AND SF1_CAB.D_E_L_E_T_ = ' '
            LEFT JOIN SD2010 SD2
                ON CV3.CV3_TABORI = 'SD2'
                AND TO_NUMBER(TRIM(CV3.CV3_RECORI) DEFAULT 0 ON CONVERSION ERROR) = SD2.R_E_C_N_O_
                AND SD2.D_E_L_E_T_ = ' '
            LEFT JOIN SF2010 SF2_ITEM
                ON SF2_ITEM.F2_FILIAL  = SD2.D2_FILIAL
                AND SF2_ITEM.F2_DOC     = SD2.D2_DOC
                AND SF2_ITEM.F2_SERIE   = SD2.D2_SERIE
                AND SF2_ITEM.F2_CLIENTE = SD2.D2_CLIENTE
                AND SF2_ITEM.F2_LOJA    = SD2.D2_LOJA
                AND SF2_ITEM.D_E_L_E_T_ = ' '
            LEFT JOIN SF2010 SF2_CAB
                ON CV3.CV3_TABORI = 'SF2'
                AND TO_NUMBER(TRIM(CV3.CV3_RECORI) DEFAULT 0 ON CONVERSION ERROR) = SF2_CAB.R_E_C_N_O_
                AND SF2_CAB.D_E_L_E_T_ = ' '
            LEFT JOIN SA2010 SA2
                ON SA2.A2_COD  = COALESCE(SF1_ITEM.F1_FORNECE, SF1_CAB.F1_FORNECE)
                AND SA2.A2_LOJA = COALESCE(SF1_ITEM.F1_LOJA,    SF1_CAB.F1_LOJA)
                AND SA2.D_E_L_E_T_ = ' '
            LEFT JOIN SA1010 SA1
                ON SA1.A1_COD  = COALESCE(SF2_ITEM.F2_CLIENTE, SF2_CAB.F2_CLIENTE)
                AND SA1.A1_LOJA = COALESCE(SF2_ITEM.F2_LOJA,    SF2_CAB.F2_LOJA)
                AND SA1.D_E_L_E_T_ = ' '
        WHERE CT2.CT2_DATA BETWEEN :data_inicio AND :data_fim
          AND CT2.D_E_L_E_T_ = ' '
    """
    def _bater():
        """Helper local: heartbeat se ctx foi passado, senão no-op."""
        if ctx is not None:
            try:
                ctx.heartbeat()
            except Exception:
                pass

    t_conn = time.monotonic()
    conn = get_oracle_connection()
    log.warning("[CT2010 DIAG] conexão aberta em %.1fs", time.monotonic() - t_conn)
    try:
        t_exec = time.monotonic()
        cur = conn.cursor()
        # Sugere pro oracledb buscar mais linhas por round-trip, reduzindo
        # viagens de rede. Oracledb default é 100, aqui subimos pra 5k.
        try:
            cur.arraysize = _FETCH_BATCH
            cur.prefetchrows = _FETCH_BATCH + 1
        except Exception:
            pass
        cur.execute(query, {"data_inicio": data_inicio, "data_fim": data_fim})
        colunas = [d[0] for d in cur.description] if cur.description else []
        log.warning(
            "[CT2010 DIAG] execute() voltou em %.1fs — cursor aberto, %d colunas",
            time.monotonic() - t_exec, len(colunas),
        )

        # Primeiro heartbeat: Oracle já pelo menos abriu o cursor.
        _bater()

        batches: list[list[tuple]] = []
        batch_num = 0
        total_linhas = 0
        t_total = time.monotonic()
        while True:
            t_batch = time.monotonic()
            lote = cur.fetchmany(_FETCH_BATCH)
            dt = time.monotonic() - t_batch
            if not lote:
                log.warning(
                    "[CT2010 DIAG] fim do cursor após %d batches / %d linhas / %.1fs totais",
                    batch_num, total_linhas, time.monotonic() - t_total,
                )
                break
            batch_num += 1
            total_linhas += len(lote)
            # Loga todos os batches lentos (>5s) e um a cada 10 pra ter traça.
            if dt > 5.0 or batch_num % 10 == 0:
                log.warning(
                    "[CT2010 DIAG] batch #%d: %d linhas em %.2fs (acumulado: %d linhas / %.1fs)",
                    batch_num, len(lote), dt, total_linhas,
                    time.monotonic() - t_total,
                )
            batches.append(lote)
            _bater()

        # Monta o DataFrame de uma só vez — bem mais barato que concat
        # de vários pequenos. Lista de tuples já vem no formato nativo.
        t_df = time.monotonic()
        if batches:
            # Achata lista de lotes em uma só sequência de linhas.
            linhas = [row for lote in batches for row in lote]
            df = pd.DataFrame(linhas, columns=colunas)
        else:
            df = pd.DataFrame(columns=colunas)
        log.warning(
            "[CT2010 DIAG] DataFrame montado em %.1fs (%d linhas)",
            time.monotonic() - t_df, len(df),
        )
    finally:
        try:
            conn.close()
        except Exception:
            pass

    _bater()

    for col in ["CT2_FILIAL", "CT2_LOTE", "NUMERO_NF", "SERIE_NF", "CLI_FOR", "LOJA"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    return df
