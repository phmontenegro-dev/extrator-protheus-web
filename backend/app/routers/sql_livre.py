"""
Endpoints de SQL livre — consulta Oracle ad-hoc com validação defensiva.

  POST /sql-livre/executar     → executa SELECT, retorna JSON com preview
  POST /sql-livre/download     → executa SELECT, retorna CSV sem limite

Autorização: admin passa; não-admin precisa ter 'codigo_sql' em permissoes
(mesmo modelo do Relatório Livre).

Camadas de defesa (mesmo o usuário Oracle sendo read-only):
  - Validador recusa qualquer coisa que não seja SELECT/WITH
  - Validador rejeita palavras DDL/DML/execução procedural
  - Validador rejeita múltiplas sentenças
  - Timeout curto de 240s (vs 600s dos relatórios programados)
  - Toda execução vai pra logs_acesso com o texto do SQL e duração
"""
import csv
import io
import time
from datetime import datetime

import oracledb
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_usuario_atual
from app.database import get_db
from app.models.usuario import Usuario
from app.oracle import get_oracle_connection
from app.schemas.sql_livre import (
    SqlDownloadPayload,
    SqlExecutarPayload,
    SqlExecutarResponse,
)
from app.utils import logs
from app.utils.permissoes import pode_acessar
from app.utils.sql_validator import SqlInvalidoError, validar_sql


RELATORIO_ID = "codigo_sql"
TIMEOUT_SEGUNDOS = 240   # 4 minutos — menor que o default de 600s dos relatórios

router = APIRouter(prefix="/sql-livre", tags=["sql-livre"])


def _exigir_permissao(db: Session, usuario: Usuario, request: Request) -> None:
    """Checa permissão e registra log de acesso negado quando bloqueia."""
    if not pode_acessar(db, usuario, RELATORIO_ID):
        logs.registrar(
            db, acao="acesso_negado", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=RELATORIO_ID, sucesso=False,
            erro_mensagem="sem permissão para codigo_sql",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para executar SQL livre.",
        )


def _validar_ou_422(sql: str) -> str:
    """Wrapper que converte SqlInvalidoError em HTTP 422 com mensagem clara."""
    try:
        return validar_sql(sql)
    except SqlInvalidoError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(e))


# Limite de caracteres pra CLOB/NCLOB — valores maiores são truncados.
# 20000 é generoso pra observação por humano mas protege o JSON de ficar MB.
_LOB_CHARS_MAX = 20_000


def _normalizar_valor(v):
    """Converte valores Oracle pra tipos serializáveis em JSON/CSV.

    Pontos-chave:
      - LOB (CLOB/NCLOB/BLOB) é um objeto lazy do oracledb — precisa .read().
        CLOB/NCLOB viram string (truncada em _LOB_CHARS_MAX).
        BLOB vira "<binário omitido>" pra não vazar MB no JSON.
      - bytes/bytearray também são binários diretos — mesma política.
      - datetime vira string ISO-like formatável no Excel.
    """
    if v is None:
        return None
    # LOB — precisa ler ANTES de verificar tipos primitivos, pois oracledb.LOB
    # não é instance de bytes/str.
    if isinstance(v, oracledb.LOB):
        try:
            tipo = v.type
            if tipo in (oracledb.DB_TYPE_CLOB, oracledb.DB_TYPE_NCLOB):
                s = v.read() or ""
                if len(s) > _LOB_CHARS_MAX:
                    return s[:_LOB_CHARS_MAX] + "...<truncado>"
                return s
            # BLOB ou RAW grande: não serializa o binário
            return "<binário omitido>"
        except Exception:
            return "<lob não pôde ser lido>"
    if isinstance(v, (bytes, bytearray)):
        # RAW/BLOB em caminho síncrono também cai aqui.
        return "<binário omitido>"
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    return v


@router.post("/executar", response_model=SqlExecutarResponse)
def executar(
    payload: SqlExecutarPayload,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> SqlExecutarResponse:
    """
    Executa um SELECT e devolve preview (JSON). Limitado a `limite_preview`
    linhas; se o resultado tem mais, vem `truncado=true` e o usuário pode
    optar por baixar o CSV completo via /download.
    """
    _exigir_permissao(db, usuario, request)
    sql_limpo = _validar_ou_422(payload.sql)

    inicio = time.monotonic()
    conn = None
    try:
        conn = get_oracle_connection(timeout_s=TIMEOUT_SEGUNDOS)
        cur = conn.cursor()
        cur.execute(sql_limpo)

        colunas = [d[0] for d in cur.description] if cur.description else []
        # fetchmany com N+1 pra detectar "tem mais depois"
        brutas = cur.fetchmany(payload.limite_preview + 1)
        truncado = len(brutas) > payload.limite_preview
        linhas = [[_normalizar_valor(v) for v in r] for r in brutas[: payload.limite_preview]]

        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logs.registrar(
            db, acao="sql_livre_executar", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=RELATORIO_ID,
            parametros={"sql": sql_limpo[:2000], "limite_preview": payload.limite_preview},
            registros_retornados=len(linhas),
            duracao_ms=duracao_ms,
            sucesso=True,
        )
        return SqlExecutarResponse(
            colunas=colunas,
            linhas=linhas,
            total=len(linhas),
            truncado=truncado,
            duracao_ms=duracao_ms,
        )
    except HTTPException:
        raise
    except Exception as e:
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logs.registrar(
            db, acao="sql_livre_executar", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=RELATORIO_ID,
            parametros={"sql": sql_limpo[:2000]},
            duracao_ms=duracao_ms, sucesso=False,
            erro_mensagem=str(e)[:2000],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro na consulta: {e}",
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


@router.post("/download")
def download(
    payload: SqlDownloadPayload,
    request: Request,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_usuario_atual),
) -> StreamingResponse:
    """
    Executa um SELECT e devolve CSV completo (sem limite de linhas, só o
    timeout do Oracle). Útil pra puxar resultados grandes direto pro Excel.
    """
    _exigir_permissao(db, usuario, request)
    sql_limpo = _validar_ou_422(payload.sql)

    nome = (payload.nome_arquivo or "consulta_sql").strip()
    if not nome.lower().endswith(".csv"):
        nome += ".csv"

    inicio = time.monotonic()
    conn = None
    try:
        conn = get_oracle_connection(timeout_s=TIMEOUT_SEGUNDOS)
        cur = conn.cursor()
        cur.execute(sql_limpo)

        colunas = [d[0] for d in cur.description] if cur.description else []

        # Serializa CSV em memória. Pra volumes muito grandes, migrar pra
        # streaming direto do cursor (gerador que faz fetchmany em batches).
        buffer = io.StringIO()
        # BOM UTF-8 pra Excel abrir certo
        buffer.write("﻿")
        writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(colunas)

        total = 0
        while True:
            lote = cur.fetchmany(5000)
            if not lote:
                break
            for row in lote:
                writer.writerow([_normalizar_valor(v) for v in row])
                total += 1

        conteudo = buffer.getvalue().encode("utf-8")

        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logs.registrar(
            db, acao="sql_livre_download", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=RELATORIO_ID,
            parametros={"sql": sql_limpo[:2000], "nome_arquivo": nome},
            registros_retornados=total, duracao_ms=duracao_ms, sucesso=True,
        )

        return StreamingResponse(
            iter([conteudo]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{nome}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logs.registrar(
            db, acao="sql_livre_download", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=RELATORIO_ID,
            parametros={"sql": sql_limpo[:2000]},
            duracao_ms=duracao_ms, sucesso=False,
            erro_mensagem=str(e)[:2000],
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Erro na consulta: {e}",
        )
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
