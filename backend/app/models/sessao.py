from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Sessao(Base):
    """
    Sessões ativas (login via cookie httpOnly).

    Guardamos o token aqui para poder revogar remotamente: logout de outros
    dispositivos, invalidar sessão em caso de incidente, etc.
    """
    __tablename__ = "sessoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Token longo e opaco (gerado com secrets.token_urlsafe).
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_origem: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"<Sessao id={self.id} usuario_id={self.usuario_id}>"
