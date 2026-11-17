from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Area(Base):
    """
    Áreas (categorias) que agrupam relatórios no menu.
    Admin cria/edita/ordena pela tela /admin/areas.
    """
    __tablename__ = "areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    descricao: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Menor ordem aparece primeiro no menu. Áreas com mesma ordem são
    # ordenadas por id secundariamente.
    ordem: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Area id={self.id} nome={self.nome!r}>"
