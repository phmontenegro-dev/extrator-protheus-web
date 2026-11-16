from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ----- Usuários -----

class UsuarioCreate(BaseModel):
    """Payload de criação de usuário por admin."""
    username: str = Field(min_length=1, max_length=100)
    nome_completo: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=200)
    senha: str = Field(min_length=1, max_length=200)
    is_admin: bool = False
    # Permissões iniciais (lista de relatorio_id). Ignorado se is_admin=True.
    permissoes: list[str] = Field(default_factory=list)


class UsuarioUpdate(BaseModel):
    """Campos editáveis — todos opcionais, só os enviados são aplicados."""
    nome_completo: Optional[str] = Field(default=None, min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=200)
    is_admin: Optional[bool] = None
    ativo: Optional[bool] = None


class ResetSenhaPayload(BaseModel):
    nova_senha: str = Field(min_length=1, max_length=200)


class UsuarioDetalhe(BaseModel):
    """Visão administrativa do usuário (nunca inclui hash)."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nome_completo: str
    email: Optional[str] = None
    is_admin: bool
    ativo: bool
    criado_em: datetime
    ultimo_login: Optional[datetime] = None


# ----- Permissões -----

class PermissoesPayload(BaseModel):
    """Lista de relatorio_ids que o usuário passa a ter. Substitui a anterior."""
    relatorios: list[str] = Field(default_factory=list)


class PermissoesResponse(BaseModel):
    usuario_id: int
    relatorios: list[str]


# ----- Logs -----

class LogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    timestamp: datetime
    usuario_id: Optional[int] = None
    username: Optional[str] = None
    acao: str
    relatorio_id: Optional[str] = None
    parametros: Optional[dict] = None
    registros_retornados: Optional[int] = None
    duracao_ms: Optional[int] = None
    ip_origem: Optional[str] = None
    sucesso: bool
    erro_mensagem: Optional[str] = None


class LogsPagina(BaseModel):
    itens: list[LogItem]
    total: int
    limit: int
    offset: int
