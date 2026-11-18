"""
Schemas Pydantic dos endpoints /jobs.

Separados dos modelos ORM pra garantir que só campos seguros vão pro JSON
(ex: `caminho_csv` nunca escapa — é caminho de servidor).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class JobResumo(BaseModel):
    """Resposta da listagem (/jobs) e do GET /jobs/{id}."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    usuario_id: Optional[int]
    username: Optional[str]
    tipo: str
    relatorio_id: str
    titulo: str
    status: str
    progresso_pct: int
    total_linhas: Optional[int]
    tamanho_bytes: Optional[int]
    nome_arquivo: Optional[str]
    erro_mensagem: Optional[str]
    duracao_estimada_s: Optional[int]
    criado_em: datetime
    iniciado_em: Optional[datetime]
    concluido_em: Optional[datetime]

    @property
    def duracao_ms(self) -> Optional[int]:
        # pydantic ignora property; o cliente calcula do iniciado_em/concluido_em.
        return None


class JobCriadoResponse(BaseModel):
    """Resposta dos endpoints -async que só enfileiram o job."""
    job_id: str
    status: str
    posicao_fila: Optional[int] = None  # None = já rodando ou sem fila
    mensagem: str
