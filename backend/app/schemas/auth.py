import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator


# Regex simples pra validar email — não é perfeita (o RFC completo é
# praticamente irrealizável), mas pega 99% dos erros do dia a dia.
# Evita adicionar a dep `email-validator` do pydantic só por isso.
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


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


# ---- Perfil do próprio usuário (Etapa 17) ----

class AtualizarPerfilPayload(BaseModel):
    """
    Edita campos do próprio usuário. Username NÃO é editável (é identificador).
    Pra editar, exige a senha atual como confirmação (defense-in-depth —
    evita sequestro de email em sessão deixada aberta).
    """
    nome_completo: str = Field(min_length=1, max_length=200)
    email: Optional[str] = Field(default=None, max_length=200)
    senha_atual: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _valida_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        v = v.strip()
        if not _EMAIL_RE.match(v):
            raise ValueError("Email com formato inválido.")
        return v


class TrocarSenhaPayload(BaseModel):
    """
    Trocar senha exige a senha atual (confirmação). A nova senha passa pela
    mesma política de login (8+ chars, 1 caractere especial).

    Após trocar, todas as sessões do usuário são revogadas, exceto a atual —
    isso desloga o usuário em outros dispositivos onde ele possa ter esquecido
    aberto, ou em caso de suspeita de invasão.
    """
    senha_atual: str = Field(min_length=1, max_length=200)
    senha_nova: str = Field(min_length=8, max_length=200)


class TrocarSenhaResponse(BaseModel):
    ok: bool
    sessoes_revogadas: int
