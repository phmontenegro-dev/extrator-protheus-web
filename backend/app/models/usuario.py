from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    nome_completo: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    senha_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ultimo_login: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relacionamentos (opcional nesta etapa, útil na Etapa 2)
    permissoes: Mapped[list["PermissaoRelatorio"]] = relationship(  # noqa: F821
        back_populates="usuario",
        cascade="all, delete-orphan",
        foreign_keys="PermissaoRelatorio.usuario_id",
    )

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} username={self.username!r}>"
