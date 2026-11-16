from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class TabelaInfo(BaseModel):
    """Entrada da listagem de tabelas."""
    nome: str
    descricao: Optional[str] = None       # vem do TABELAS_CONHECIDAS, se cadastrada
    campo_data_sugerido: Optional[str] = None


class ColunasResponse(BaseModel):
    tabela: str
    colunas: list[str]


class FiltrosLivre(BaseModel):
    """Payload de extração do Relatório Livre."""
    tabela: str = Field(min_length=1, max_length=50)
    colunas: list[str] = Field(min_length=1)
    # None = sem filtro de data (e nesse caso data_inicio/data_fim são ignoradas)
    campo_data: Optional[str] = None
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    # Limite opcional via ROWNUM. None = sem limite.
    max_linhas: Optional[int] = Field(default=None, gt=0, le=1_000_000)

    @model_validator(mode="after")
    def _valida(self):
        if self.campo_data:
            if not self.data_inicio or not self.data_fim:
                raise ValueError(
                    "Quando 'campo_data' for informado, 'data_inicio' e 'data_fim' são obrigatórias."
                )
            if self.data_inicio > self.data_fim:
                raise ValueError("data_inicio não pode ser maior que data_fim")
        return self

    def datas_aaaammdd(self) -> tuple[Optional[str], Optional[str]]:
        if not self.campo_data or not self.data_inicio or not self.data_fim:
            return None, None
        return (
            self.data_inicio.strftime("%Y%m%d"),
            self.data_fim.strftime("%Y%m%d"),
        )
