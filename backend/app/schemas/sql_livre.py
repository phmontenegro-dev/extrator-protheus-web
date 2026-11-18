from typing import Any, Optional
from pydantic import BaseModel, Field


class SqlExecutarPayload(BaseModel):
    """SQL a executar no modo preview (JSON response)."""
    sql: str = Field(min_length=1, max_length=50_000)
    # Limite de linhas no preview. Default 500.
    limite_preview: int = Field(default=500, ge=1, le=5000)


class SqlExecutarResponse(BaseModel):
    colunas: list[str]
    linhas: list[list[Any]]
    total: int                    # qtd efetiva retornada (até limite_preview)
    truncado: bool                # True se havia mais linhas e paramos
    duracao_ms: int


class SqlDownloadPayload(BaseModel):
    """SQL a executar no modo download (CSV response sem limite)."""
    sql: str = Field(min_length=1, max_length=50_000)
    nome_arquivo: Optional[str] = Field(default=None, max_length=200)
