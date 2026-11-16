from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LogAcesso(Base):
    """
    Registro central de auditoria do sistema.

    Toda ação relevante gera uma linha aqui: login, extração de relatório,
    acesso negado, erro, etc. Guardamos username como texto solto (além do FK)
    para que o log faça sentido mesmo depois de uma eventual deleção do
    usuário.
    """
    __tablename__ = "logs_acesso"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    usuario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True
    )
    # Guardado solto também — sobrevive a deleção do usuário.
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Tipo de ação. Exemplos:
    #   "login_ok", "login_falhou", "logout",
    #   "extrair_relatorio", "download_csv",
    #   "acesso_negado", "erro"
    acao: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Quando a ação é sobre um relatório.
    relatorio_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    # Filtros usados (datas, filial, etc) como JSON.
    parametros: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    registros_retornados: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duracao_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    ip_origem: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    erro_mensagem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<LogAcesso id={self.id} acao={self.acao!r} username={self.username!r}>"
