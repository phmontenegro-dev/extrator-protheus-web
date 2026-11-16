from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PermissaoRelatorio(Base):
    __tablename__ = "permissoes_relatorio"
    __table_args__ = (
        UniqueConstraint("usuario_id", "relatorio_id", name="uq_usuario_relatorio"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(
        ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # ID textual do relatório (igual ao registry.py do desktop).
    # Ex.: "ct2010", "sb8_suzano", "relatorio_livre".
    relatorio_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    concedido_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    concedido_por_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )

    usuario: Mapped["Usuario"] = relationship(  # noqa: F821
        back_populates="permissoes",
        foreign_keys=[usuario_id],
    )

    def __repr__(self) -> str:
        return f"<Permissao usuario_id={self.usuario_id} relatorio_id={self.relatorio_id!r}>"
