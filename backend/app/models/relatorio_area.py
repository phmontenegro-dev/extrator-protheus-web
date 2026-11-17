from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RelatorioArea(Base):
    """
    Atribuição de um relatório a uma área.

    `relatorio_id` é a string do registry (ex: "ct2010"). É UNIQUE porque
    cada relatório fica em NO MÁXIMO uma área (decisão de UX — menu limpo).
    """
    __tablename__ = "relatorio_areas"

    id: Mapped[int] = mapped_column(primary_key=True)
    relatorio_id: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    area_id: Mapped[int] = mapped_column(
        ForeignKey("areas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<RelatorioArea relatorio={self.relatorio_id!r} area_id={self.area_id}>"
