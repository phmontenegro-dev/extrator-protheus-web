from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


class RelatorioInfo(BaseModel):
    """Metadados de um relatório, exibido na lista."""
    id: str
    nome: str
    descricao: str
    # Tipo de filtros que o frontend precisa renderizar.
    # Deve ficar em sincronia com TipoFiltro em relatorios_prontos/registry.py.
    filtros: Literal["nenhum", "periodo", "filial_periodo", "livre", "sql"]
    # Área a que o relatório foi atribuído pelo admin (nullable → "Outros").
    # O frontend agrupa o menu por essa info; ordenação segue area_ordem.
    area_id: Optional[int] = None
    area_nome: Optional[str] = None
    area_ordem: Optional[int] = None


# ---- Modelos de filtros ----

class FiltrosPeriodo(BaseModel):
    """Data inicial + final, no formato ISO (YYYY-MM-DD)."""
    data_inicio: date
    data_fim: date = Field(description="Deve ser >= data_inicio")

    @model_validator(mode="after")
    def _valida_intervalo(self):
        if self.data_inicio > self.data_fim:
            raise ValueError("data_inicio não pode ser maior que data_fim")
        return self

    def para_aaaammdd(self) -> tuple[str, str]:
        """Converte para o formato usado pelo Protheus."""
        return (
            self.data_inicio.strftime("%Y%m%d"),
            self.data_fim.strftime("%Y%m%d"),
        )


class FiltrosFilialPeriodo(FiltrosPeriodo):
    """Filial + data_inicio + data_fim. Usado pelo QPR010."""
    filial: str = Field(min_length=1, max_length=20)


# Alias retrocompatível (a Etapa 3 e 4 importavam CT2010Filtros).
CT2010Filtros = FiltrosPeriodo
