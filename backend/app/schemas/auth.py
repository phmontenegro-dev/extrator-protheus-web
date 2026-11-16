from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    senha: str = Field(min_length=1, max_length=200)


class UsuarioOut(BaseModel):
    """Representação pública do usuário — nunca inclui senha_hash."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nome_completo: str
    email: Optional[str] = None
    is_admin: bool
    ativo: bool
    criado_em: datetime
    ultimo_login: Optional[datetime] = None


class LoginResponse(BaseModel):
    ok: bool
    usuario: UsuarioOut


class LogoutResponse(BaseModel):
    ok: bool
