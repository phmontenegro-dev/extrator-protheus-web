"""
Endpoint /health — verifica conectividade com os dois bancos.

Objetivo nesta Etapa 1: ser o "hello world" ponta a ponta. O frontend chama
este endpoint e mostra o resultado na tela. Se estiver tudo verde, a base
está sólida pra seguir pra Etapa 2.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.oracle import testar_conexao as testar_oracle
from app.schemas.health import HealthResponse, ServicoStatus


router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    settings = get_settings()

    # Postgres
    try:
        db.execute(text("SELECT 1"))
        pg_status = ServicoStatus(ok=True, detalhe="conectado")
    except Exception as e:
        pg_status = ServicoStatus(ok=False, detalhe=f"erro: {e!s}")

    # Oracle
    try:
        ok = testar_oracle()
        oracle_status = ServicoStatus(
            ok=ok,
            detalhe="conectado" if ok else "resposta inesperada",
        )
    except Exception as e:
        oracle_status = ServicoStatus(ok=False, detalhe=f"erro: {e!s}")

    return HealthResponse(
        ok=pg_status.ok and oracle_status.ok,
        ambiente=settings.env,
        postgres=pg_status,
        oracle=oracle_status,
    )
