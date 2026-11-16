from typing import Optional
from pydantic import BaseModel


class ServicoStatus(BaseModel):
    ok: bool
    detalhe: Optional[str] = None


class HealthResponse(BaseModel):
    ok: bool
    ambiente: str
    postgres: ServicoStatus
    oracle: ServicoStatus
