"""
Runners de job por tipo.

Cada runner é uma função `(ctx: JobContext) -> None` que:
  1. avança o status pelos estágios
  2. extrai, trata, serializa CSV, grava em disco
  3. chama ctx.finalizar_sucesso / finalizar_erro

Reusa o máximo possível do código síncrono já existente — a extração e
o tratamento continuam sendo as funções extrair_X / tratar_X.
"""
import csv as _csv
import io
import logging
import os
from datetime import datetime
from typing import Any

from app.jobs.executor import JobContext, caminho_do_csv
from app.models.job import (
    STATUS_CONSULTANDO,
    STATUS_ESCREVENDO,
    STATUS_TRATANDO,
)
from app.oracle import get_oracle_connection
from app.relatorio_livre.extrair import extrair as extrair_livre
from app.relatorios_prontos.ct2010.extrair import extrair_ct2010
from app.relatorios_prontos.ct2010.tratar import tratar_dataframe as tratar_ct2010
from app.relatorios_prontos.qpr010.extrair import extrair_qpr010
from app.relatorios_prontos.qpr010.tratar import tratar_dataframe as tratar_qpr010
from app.relatorios_prontos.sft010.extrair import extrair_sft010
from app.relatorios_prontos.sft010.tratar import tratar_dataframe as tratar_sft010
from app.relatorios_prontos.sd3010.extrair import extrair_sd3010
from app.relatorios_prontos.sd3010.tratar import tratar_dataframe as tratar_sd3010
from app.relatorios_prontos.sb8_suzano.extrair import extrair_sb8_suzano
from app.relatorios_prontos.sb8_suzano.tratar import tratar_dataframe as tratar_sb8_suzano
from app.relatorios_prontos.sd1_suzano.extrair import extrair_sd1_suzano
from app.relatorios_prontos.sd1_suzano.tratar import tratar_dataframe as tratar_sd1_suzano
from app.relatorios_prontos.sd2_suzano.extrair import extrair_sd2_suzano
from app.relatorios_prontos.sd2_suzano.tratar import tratar_dataframe as tratar_sd2_suzano
from app.relatorios_prontos.sd4_suzano.extrair import extrair_sd4_suzano
from app.relatorios_prontos.sd4_suzano.tratar import tratar_dataframe as tratar_sd4_suzano
from app.relatorios_prontos.sh6_suzano.extrair import extrair_sh6_suzano
from app.relatorios_prontos.sh6_suzano.tratar import tratar_dataframe as tratar_sh6_suzano
from app.relatorios_prontos.consolidado_suzano_jhon.extrair import extrair_consolidado_suzano_jhon
from app.relatorios_prontos.consolidado_suzano_jhon.tratar import tratar_dataframe as tratar_consolidado_suzano_jhon
from app.relatorios_prontos.paradas_maquina.extrair import extrair_paradas_maquina
from app.relatorios_prontos.paradas_maquina.tratar import tratar_dataframe as tratar_paradas_maquina
from app.relatorios_prontos.sh6_produtivolote.extrair import extrair_sh6_produtivolote
from app.relatorios_prontos.sh6_produtivolote.tratar import tratar_dataframe as tratar_sh6_produtivolote

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Registry de relatórios prontos: id → (extrair_fn_factory, tratar_fn)
# -----------------------------------------------------------------------------
#
# extrair_fn_factory recebe o dict de filtros e devolve a closure a ser
# chamada (que já embute os parâmetros). Isso mantém a assinatura uniforme
# do runner.
# -----------------------------------------------------------------------------

def _f_ct2010(f: dict):
    return lambda: extrair_ct2010(f["data_inicio"], f["data_fim"])
def _f_qpr010(f: dict):
    return lambda: extrair_qpr010(f["filial"], f["data_inicio"], f["data_fim"])
def _f_sft010(f: dict):
    return lambda: extrair_sft010(f["data_inicio"], f["data_fim"])
def _f_sd3010(f: dict):
    return lambda: extrair_sd3010(f["data_inicio"], f["data_fim"])
def _f_sd4_suzano(f: dict):
    return lambda: extrair_sd4_suzano(f["data_inicio"], f["data_fim"])
def _f_sh6_suzano(f: dict):
    return lambda: extrair_sh6_suzano(f["data_inicio"], f["data_fim"])
def _f_consolidado(f: dict):
    return lambda: extrair_consolidado_suzano_jhon(f["data_inicio"], f["data_fim"])
def _f_paradas(f: dict):
    return lambda: extrair_paradas_maquina(f["data_inicio"], f["data_fim"])
def _f_sb8(f: dict):
    return lambda: extrair_sb8_suzano()
def _f_sd1(f: dict):
    return lambda: extrair_sd1_suzano()
def _f_sd2(f: dict):
    return lambda: extrair_sd2_suzano()
def _f_sh6_produtivolote(f: dict):
    return lambda: extrair_sh6_produtivolote(f["data_inicio"], f["data_fim"])


RUNNERS_PRONTOS: dict[str, tuple[Any, Any]] = {
    "ct2010": (_f_ct2010, tratar_ct2010),
    "qpr010": (_f_qpr010, tratar_qpr010),
    "sft010": (_f_sft010, tratar_sft010),
    "sd3010": (_f_sd3010, tratar_sd3010),
    "sb8_suzano": (_f_sb8, tratar_sb8_suzano),
    "sd1_suzano": (_f_sd1, tratar_sd1_suzano),
    "sd2_suzano": (_f_sd2, tratar_sd2_suzano),
    "sd4_suzano": (_f_sd4_suzano, tratar_sd4_suzano),
    "sh6_suzano": (_f_sh6_suzano, tratar_sh6_suzano),
    "consolidado_suzano_jhon": (_f_consolidado, tratar_consolidado_suzano_jhon),
    "paradas_maquina": (_f_paradas, tratar_paradas_maquina),
    "sh6_produtivolote": (_f_sh6_produtivolote, tratar_sh6_produtivolote),
}


# -----------------------------------------------------------------------------
# Runner: relatório pronto
# -----------------------------------------------------------------------------

def runner_relatorio_pronto(
    relatorio_id: str, filtros: dict, nome_arquivo: str
):
    """
    Factory que devolve um runner pronto pra ser passado ao executor.

    Fecha sobre o id do relatório, os filtros a aplicar e o nome do CSV final.
    """
    if relatorio_id not in RUNNERS_PRONTOS:
        raise ValueError(f"relatório desconhecido: {relatorio_id}")
    factory_extrair, tratar_fn = RUNNERS_PRONTOS[relatorio_id]

    def _run(ctx: JobContext) -> None:
        ctx.avancar(STATUS_CONSULTANDO)
        df = factory_extrair(filtros)()

        if df is None or df.empty:
            ctx.finalizar_erro("Nenhum registro encontrado para os filtros informados.")
            return

        ctx.avancar(STATUS_TRATANDO)
        if tratar_fn is not None:
            df = tratar_fn(df)

        ctx.avancar(STATUS_ESCREVENDO)
        caminho = caminho_do_csv(ctx.job_id)
        # chunksize=20000: pandas serializa em blocos, liberando buffers de
        # string entre eles. Reduz pico de RAM em ~30-40% em relação a
        # dump único, especialmente em DataFrames largos com muita coluna texto.
        df.to_csv(
            caminho, index=False, sep=";", encoding="utf-8-sig", chunksize=20000
        )
        tamanho = os.path.getsize(caminho)

        ctx.finalizar_sucesso(
            caminho_csv=caminho,
            nome_arquivo=nome_arquivo,
            total_linhas=len(df),
            tamanho_bytes=tamanho,
        )

    return _run


# -----------------------------------------------------------------------------
# Runner: relatório livre
# -----------------------------------------------------------------------------

def runner_relatorio_livre(filtros: dict, nome_arquivo: str):
    """
    filtros precisa ter: tabela, colunas (list), campo_data (opcional),
    data_inicio (opcional), data_fim (opcional), max_linhas (opcional).
    """

    def _run(ctx: JobContext) -> None:
        ctx.avancar(STATUS_CONSULTANDO)
        df = extrair_livre(
            tabela=filtros["tabela"],
            colunas=filtros.get("colunas", []),
            campo_data=filtros.get("campo_data"),
            data_inicio=filtros.get("data_inicio"),
            data_fim=filtros.get("data_fim"),
            max_linhas=filtros.get("max_linhas"),
        )

        if df is None or df.empty:
            ctx.finalizar_erro("Nenhum registro encontrado para os filtros informados.")
            return

        # Livre não aplica tratamento (extração crua).
        ctx.avancar(STATUS_ESCREVENDO)
        caminho = caminho_do_csv(ctx.job_id)
        df.to_csv(
            caminho, index=False, sep=";", encoding="utf-8-sig", chunksize=20000
        )
        tamanho = os.path.getsize(caminho)

        ctx.finalizar_sucesso(
            caminho_csv=caminho,
            nome_arquivo=nome_arquivo,
            total_linhas=len(df),
            tamanho_bytes=tamanho,
        )

    return _run


# -----------------------------------------------------------------------------
# Runner: código SQL
# -----------------------------------------------------------------------------

def _normalizar_valor(v):
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        return "<binário omitido>"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


def runner_codigo_sql(sql_limpo: str, nome_arquivo: str, timeout_s: int):
    """
    Executa o SELECT em streaming e escreve o CSV direto no disco em batches
    de 5000 linhas — assim consultas grandes não estouram a memória.
    """

    def _run(ctx: JobContext) -> None:
        ctx.avancar(STATUS_CONSULTANDO)
        conn = get_oracle_connection(timeout_s=timeout_s)
        try:
            cur = conn.cursor()
            cur.execute(sql_limpo)
            colunas = [d[0] for d in cur.description] if cur.description else []

            ctx.avancar(STATUS_ESCREVENDO)
            caminho = caminho_do_csv(ctx.job_id)
            total = 0
            with open(caminho, "w", encoding="utf-8", newline="") as f:
                # BOM UTF-8 pra Excel abrir certo
                f.write("﻿")
                writer = _csv.writer(f, delimiter=";", quoting=_csv.QUOTE_MINIMAL)
                writer.writerow(colunas)
                while True:
                    lote = cur.fetchmany(5000)
                    if not lote:
                        break
                    for row in lote:
                        writer.writerow([_normalizar_valor(v) for v in row])
                        total += 1

            if total == 0:
                # Apaga o CSV só com o header e marca como erro — comportamento
                # consistente com os outros runners.
                try:
                    os.remove(caminho)
                except Exception:
                    pass
                ctx.finalizar_erro("Nenhum registro retornado pela consulta.")
                return

            tamanho = os.path.getsize(caminho)
            ctx.finalizar_sucesso(
                caminho_csv=caminho,
                nome_arquivo=nome_arquivo,
                total_linhas=total,
                tamanho_bytes=tamanho,
            )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    return _run
