"""
Helper central para executar relatório + devolver CSV + gravar log.

Cada endpoint de relatório chama `executar_e_responder_csv(...)` passando a
função de extração, a função de tratamento e os parâmetros. O helper cuida de:
  - cronometrar
  - validar permissão (admin passa; não-admin precisa estar em permissoes)
  - executar extração
  - aplicar tratamento (se houver)
  - serializar CSV em memória
  - montar StreamingResponse com Content-Disposition e expose header
  - gravar log de sucesso / sem registros / erro

Isso tira ~40 linhas repetidas de cada endpoint.
"""
import time
from io import BytesIO
from typing import Callable, Optional

import pandas as pd
from fastapi import HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.usuario import Usuario
from app.utils import logs
from app.utils.permissoes import pode_acessar


def executar_e_responder_csv(
    *,
    db: Session,
    request: Request,
    usuario: Usuario,
    relatorio_id: str,
    nome_arquivo: str,
    extrair_fn: Callable[[], pd.DataFrame],
    tratar_fn: Optional[Callable[[pd.DataFrame], pd.DataFrame]] = None,
    parametros_log: Optional[dict] = None,
) -> StreamingResponse:
    """
    Fluxo completo de extração e resposta.

    extrair_fn: callable sem argumentos (use closure) que retorna o DataFrame bruto.
    tratar_fn:  opcional — recebe o df bruto e devolve o tratado.
    nome_arquivo: filename com .csv final (ex: "QPR010_0101001_20260101_a_20260131.csv").
    """
    # 1) Permissão
    if not pode_acessar(db, usuario, relatorio_id):
        logs.registrar(
            db, acao="acesso_negado", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=relatorio_id, sucesso=False,
            erro_mensagem=f"sem permissão para {relatorio_id}",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não tem permissão para este relatório.",
        )

    inicio = time.monotonic()
    try:
        df = extrair_fn()

        if df is None or df.empty:
            duracao_ms = int((time.monotonic() - inicio) * 1000)
            logs.registrar(
                db, acao="extrair_relatorio", request=request,
                usuario_id=usuario.id, username=usuario.username,
                relatorio_id=relatorio_id, parametros=parametros_log,
                registros_retornados=0, duracao_ms=duracao_ms,
                sucesso=True, erro_mensagem="sem registros no período",
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nenhum registro encontrado para os filtros informados.",
            )

        if tratar_fn is not None:
            df = tratar_fn(df)

        # Serializa CSV em memória. Para volumes muito grandes, migrar para
        # streaming direto do cursor — por ora todos os relatórios cabem.
        buffer = BytesIO()
        df.to_csv(buffer, index=False, sep=";", encoding="utf-8-sig")
        conteudo = buffer.getvalue()

        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logs.registrar(
            db, acao="extrair_relatorio", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=relatorio_id, parametros=parametros_log,
            registros_retornados=len(df), duracao_ms=duracao_ms,
            sucesso=True,
        )

        return StreamingResponse(
            iter([conteudo]),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{nome_arquivo}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        duracao_ms = int((time.monotonic() - inicio) * 1000)
        logs.registrar(
            db, acao="extrair_relatorio", request=request,
            usuario_id=usuario.id, username=usuario.username,
            relatorio_id=relatorio_id, parametros=parametros_log,
            duracao_ms=duracao_ms,
            sucesso=False, erro_mensagem=str(e)[:2000],
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na extração: {e}",
        )
