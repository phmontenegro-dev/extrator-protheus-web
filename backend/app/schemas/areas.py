from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ----- Áreas -----

class AreaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    descricao: Optional[str] = Field(default=None, max_length=500)
    ordem: int = 0


class AreaUpdate(BaseModel):
    """Campos editáveis — só os informados são aplicados."""
    nome: Optional[str] = Field(default=None, min_length=1, max_length=100)
    descricao: Optional[str] = Field(default=None, max_length=500)
    ordem: Optional[int] = None


class AreaDetalhe(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    descricao: Optional[str] = None
    ordem: int
    criado_em: datetime


class ReordenarAreasPayload(BaseModel):
    """
    Lista de IDs na ordem desejada. A primeira posição vira ordem=0,
    segunda ordem=1, etc. IDs não listados mantêm a ordem atual.
    """
    ids: list[int] = Field(default_factory=list)


# ----- Atribuição de relatórios a áreas -----

class AtribuirRelatorioPayload(BaseModel):
    """None desatribui (relatório vai pra 'Outros')."""
    area_id: Optional[int] = None


class RelatorioAreaInfo(BaseModel):
    """Retorno de GET /admin/relatorio-areas — mapa simples."""
    relatorio_id: str
    area_id: Optional[int] = None
