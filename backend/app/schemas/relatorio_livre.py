from datetime import date
from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, Field, model_validator


class TabelaInfo(BaseModel):
    """Entrada da listagem de tabelas."""
    nome: str
    descricao: Optional[str] = None       # vem do TABELAS_CONHECIDAS, se cadastrada
    campo_data_sugerido: Optional[str] = None


# ---- Colunas ----

class ColunaInfo(BaseModel):
    """Metadata de coluna — nome, tipo Oracle bruto e categoria lógica."""
    nome: str
    tipo_oracle: str
    tipo_logico: Literal["texto", "numero", "data"]


class ColunasResponse(BaseModel):
    """
    Resposta da API de colunas.

    Formato novo (Etapa 12): `colunas: list[ColunaInfo]` com tipo.
    O campo `nomes` é derivado — mantém compat com código que só olha nomes.
    """
    tabela: str
    colunas: list[ColunaInfo]

    @property
    def nomes(self) -> list[str]:
        return [c.nome for c in self.colunas]


# ---- Filtros dinâmicos (Etapa 12) ----

# Operadores suportados. O backend valida em runtime que o operador é
# compatível com o tipo_logico da coluna escolhida.
Operador = Literal[
    # texto
    "=", "<>", "contem", "comeca_com", "em_lista", "is_null", "nao_is_null",
    # numero
    ">", "<", ">=", "<=", "entre",
    # data (sobre colunas DATE do Oracle)
    "data_igual", "data_maior", "data_menor", "data_entre", "ultimos_n_dias",
]

# Operadores aceitos por tipo lógico. O backend recusa combinações inválidas.
OPERADORES_POR_TIPO: dict[str, set[str]] = {
    "texto":  {"=", "<>", "contem", "comeca_com", "em_lista", "is_null", "nao_is_null"},
    "numero": {"=", "<>", ">", "<", ">=", "<=", "entre", "is_null", "nao_is_null"},
    "data":   {"data_igual", "data_maior", "data_menor", "data_entre", "ultimos_n_dias", "is_null", "nao_is_null"},
}


class FiltroCampo(BaseModel):
    """
    Um filtro aplicado a uma coluna específica.

    `valor` interpretação por operador:
      - `entre` / `data_entre` : lista [min, max]
      - `em_lista`             : lista de strings
      - `ultimos_n_dias`       : int (nº de dias, ex: 7)
      - `is_null` / `nao_is_null` : None (ignorado)
      - demais                 : string/numero único
    """
    coluna: str = Field(min_length=1, max_length=50)
    operador: Operador
    valor: Optional[Union[str, int, float, list[Union[str, int, float]]]] = None


class FiltrosLivre(BaseModel):
    """Payload de extração do Relatório Livre."""
    tabela: str = Field(min_length=1, max_length=50)
    colunas: list[str] = Field(min_length=1)
    # None = sem filtro de data (e nesse caso data_inicio/data_fim são ignoradas).
    # Mantido por compat com a UI antiga de "campo_data + período" — convive
    # com filtros_extra sem conflito.
    campo_data: Optional[str] = None
    data_inicio: Optional[date] = None
    data_fim: Optional[date] = None
    # Filtros adicionais dinâmicos (Etapa 12). Vazio = sem filtros extras.
    filtros_extra: list[FiltroCampo] = Field(default_factory=list)
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
