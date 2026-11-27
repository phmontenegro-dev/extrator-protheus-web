"""
Runners de job por tipo.

Cada runner é uma função `(ctx: JobContext) -> None` que:
  1. avança o status pelos estágios
  2. extrai, trata, serializa CSV, grava em disco
  3. chama ctx.finalizar_sucesso / finalizar_erro

Reusa o máximo possível do código síncrono já existente — a extração e
o tratamento continuam sendo as funções extrair_X / tratar_X.

Heartbeat: durante fases pandas pesadas (groupby, concat, to_csv de
milhões de linhas) o GIL pode ficar segurado por mais de 2 minutos,
estourando o watchdog. Pra evitar, chamamos `ctx.heartbeat()`
explicitamente entre chunks do to_csv, e passamos o ctx pra funções
`tratar` que aceitam na assinatura (ver `_chamar_tratar`).
"""
import csv as _csv
import inspect
import io
import logging
import os
import time
from datetime import datetime

from app.jobs.executor import JobContext, caminho_do_csv
from app.models.job import (
    STATUS_CONSULTANDO,
    STATUS_ESCREVENDO,
    STATUS_TRATANDO,
)
from app.oracle import get_oracle_connection
from app.relatorio_livre.extrair import extrair as extrair_livre
from app.relatorios_prontos.registry import buscar_pronto

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Helpers compartilhados
# -----------------------------------------------------------------------------

# Chunksize do CSV. Buffers maiores que ~200k em DataFrame largo ficam
# caros em RAM; buffers menores que ~5k multiplicam a overhead por chunk.
# 20k é um bom meio-termo.
_CHUNK_CSV = 20_000


def _chamar_tratar(tratar_fn, df, ctx):
    """
    Chama a função de tratamento, passando `ctx` apenas se a assinatura
    aceitar — mantém compat com tratares antigos que só recebem `df`.
    """
    try:
        sig = inspect.signature(tratar_fn)
    except (TypeError, ValueError):
        return tratar_fn(df)
    if "ctx" in sig.parameters:
        return tratar_fn(df, ctx=ctx)
    return tratar_fn(df)


def _chamar_extrair(extrair_fn, filtros, ctx):
    """
    Chama a função de extração, passando `ctx` apenas se a assinatura
    aceitar. Mesmo padrão do `_chamar_tratar`: extratores antigos que
    só recebem `**filtros` seguem funcionando.
    """
    try:
        sig = inspect.signature(extrair_fn)
    except (TypeError, ValueError):
        return extrair_fn(**filtros)
    if "ctx" in sig.parameters:
        return extrair_fn(ctx=ctx, **filtros)
    # Se tem **kwargs e aceita qualquer extra, passa ctx também — permite
    # que extratores pequenos usem `**_` como catch-all e ainda recebam ctx
    # via introspecção dentro do próprio corpo (ex.: `_extrair(**_)` do
    # CT2010 que repassa pra `extrair_ct2010(..., ctx=_.get("ctx"))`).
    has_var_kw = any(
        p.kind is inspect.Parameter.VAR_KEYWORD
        for p in sig.parameters.values()
    )
    if has_var_kw:
        return extrair_fn(ctx=ctx, **filtros)
    return extrair_fn(**filtros)


def _escrever_csv_com_heartbeat(df, caminho: str, ctx) -> None:
    """
    Escreve o DataFrame em chunks, batendo heartbeat entre cada bloco.
    Isso impede que um `df.to_csv(..., chunksize=20k)` monolítico segure
    o GIL por >2min em DataFrames gigantes e seja marcado como zumbi.

    Mantém o BOM UTF-8 esperado pelo Excel (utf-8-sig equivalente).
    """
    n = len(df)
    primeira = True
    t0 = time.monotonic()
    chunk_num = 0
    # Abre em binário pra escrever o BOM manualmente antes do CSV UTF-8.
    with open(caminho, "wb") as fbin:
        fbin.write(b"\xef\xbb\xbf")  # BOM UTF-8
    # Reabre em texto pra append (mais simples do que mesclar writer + BOM).
    with open(caminho, "a", encoding="utf-8", newline="") as f:
        for ini in range(0, max(n, 1), _CHUNK_CSV):
            fim = min(ini + _CHUNK_CSV, n)
            sub = df.iloc[ini:fim]
            tc = time.monotonic()
            sub.to_csv(
                f, index=False, sep=";",
                header=primeira, encoding="utf-8",
            )
            dt = time.monotonic() - tc
            primeira = False
            chunk_num += 1
            # Loga chunks lentos (>5s) e um a cada 10 pra ter traça.
            if dt > 5.0 or chunk_num % 10 == 0:
                log.warning(
                    "[CSV DIAG job=%s] chunk #%d: %d linhas em %.2fs "
                    "(acumulado: %d/%d / %.1fs)",
                    ctx.job_id[:8], chunk_num, len(sub), dt,
                    fim, n, time.monotonic() - t0,
                )
            # Heartbeat explícito entre chunks — barato, ~1 UPDATE.
            try:
                ctx.heartbeat()
            except Exception:
                # Heartbeat é best-effort. Nunca derruba a escrita do CSV.
                log.exception("heartbeat falhou durante to_csv do job %s", ctx.job_id)
            # Se o DataFrame era vazio, sai no 1º giro.
            if n == 0:
                break
    log.warning(
        "[CSV DIAG job=%s] FIM: %d chunks, %d linhas, %.1fs totais",
        ctx.job_id[:8], chunk_num, n, time.monotonic() - t0,
    )


# -----------------------------------------------------------------------------
# Runner: relatório pronto (auto-descoberta — Etapa 11.6)
# -----------------------------------------------------------------------------
#
# Não há mais tabela RUNNERS_PRONTOS; o registro vem automaticamente do
# `app.relatorios_prontos` via base.descobrir_relatorios(). Pra adicionar
# um relatório, basta criar o arquivo/pasta correspondente exportando
# `relatorio = RelatorioPronto(...)`.
# -----------------------------------------------------------------------------

def runner_relatorio_pronto(
    relatorio_id: str, filtros: dict, nome_arquivo: str
):
    """
    Factory que devolve um runner pronto pra ser passado ao executor.

    Fecha sobre o id do relatório, os filtros a aplicar e o nome do CSV final.
    O relatório precisa estar registrado no auto-descoberta — se não estiver,
    levanta ValueError (que o dispatcher converte em erro do job).
    """
    rel = buscar_pronto(relatorio_id)
    if rel is None:
        raise ValueError(f"relatório desconhecido: {relatorio_id}")

    def _run(ctx: JobContext) -> None:
        ctx.avancar(STATUS_CONSULTANDO)
        df = _chamar_extrair(rel.extrair, filtros, ctx)

        if df is None or df.empty:
            ctx.finalizar_erro("Nenhum registro encontrado para os filtros informados.")
            return

        ctx.avancar(STATUS_TRATANDO)
        if rel.tratar is not None:
            df = _chamar_tratar(rel.tratar, df, ctx)

        ctx.avancar(STATUS_ESCREVENDO)
        caminho = caminho_do_csv(ctx.job_id)
        # Escreve em chunks com heartbeat entre cada bloco — evita que
        # to_csv monolítico de DataFrame gigante (ex: CT2010 do ano
        # inteiro) segure GIL por >2min e seja marcado como zumbi.
        _escrever_csv_com_heartbeat(df, caminho, ctx)
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
    data_inicio (opcional), data_fim (opcional), max_linhas (opcional),
    filtros_extra (opcional — list de dicts com coluna/operador/valor).
    """
    # Reidrata filtros_extra se vierem como lista de dicts (ex: agendamentos).
    from app.schemas.relatorio_livre import FiltroCampo
    raw_extra = filtros.get("filtros_extra") or []
    filtros_extra: list[FiltroCampo] = []
    for item in raw_extra:
        if isinstance(item, FiltroCampo):
            filtros_extra.append(item)
        else:
            filtros_extra.append(FiltroCampo(**item))

    def _run(ctx: JobContext) -> None:
        ctx.avancar(STATUS_CONSULTANDO)
        df = extrair_livre(
            tabela=filtros["tabela"],
            colunas=filtros.get("colunas", []),
            campo_data=filtros.get("campo_data"),
            data_inicio=filtros.get("data_inicio"),
            data_fim=filtros.get("data_fim"),
            max_linhas=filtros.get("max_linhas"),
            filtros_extra=filtros_extra,
        )

        if df is None or df.empty:
            ctx.finalizar_erro("Nenhum registro encontrado para os filtros informados.")
            return

        # Livre não aplica tratamento (extração crua).
        ctx.avancar(STATUS_ESCREVENDO)
        caminho = caminho_do_csv(ctx.job_id)
        _escrever_csv_com_heartbeat(df, caminho, ctx)
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

import oracledb

_LOB_CHARS_MAX = 20_000


def _normalizar_valor(v):
    """CLOB/BLOB viram texto (CLOB) ou placeholder (BLOB) — ver sql_livre.py."""
    if v is None:
        return None
    if isinstance(v, oracledb.LOB):
        try:
            if v.type in (oracledb.DB_TYPE_CLOB, oracledb.DB_TYPE_NCLOB):
                s = v.read() or ""
                if len(s) > _LOB_CHARS_MAX:
                    return s[:_LOB_CHARS_MAX] + "...<truncado>"
                return s
            return "<binário omitido>"
        except Exception:
            return "<lob não pôde ser lido>"
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
