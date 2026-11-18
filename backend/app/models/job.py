"""
Jobs de extração assíncrona.

Cada extração que o usuário dispara via endpoints *-async cria uma linha
aqui. O executor (app/jobs/executor.py) consome a fila e vai atualizando
status/progresso até terminar — e salva o CSV em disco.

Ciclo de vida típico:
    pendente → conectando → consultando → tratando → escrevendo → concluido

Em caso de falha: → erro (com `erro_mensagem` preenchida).
Cancelamento manual: → cancelado (só quando ainda pendente).
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, BigInteger
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


# Status possíveis. Uso string livre (não enum) pra não precisar de migration
# ao adicionar novos estados no futuro.
STATUS_PENDENTE = "pendente"
STATUS_CONECTANDO = "conectando"
STATUS_CONSULTANDO = "consultando"
STATUS_TRATANDO = "tratando"
STATUS_ESCREVENDO = "escrevendo"
STATUS_CONCLUIDO = "concluido"
STATUS_ERRO = "erro"
STATUS_CANCELADO = "cancelado"

STATUS_ATIVOS = {
    STATUS_PENDENTE,
    STATUS_CONECTANDO,
    STATUS_CONSULTANDO,
    STATUS_TRATANDO,
    STATUS_ESCREVENDO,
}
STATUS_FINAIS = {STATUS_CONCLUIDO, STATUS_ERRO, STATUS_CANCELADO}

# Tipos de job
TIPO_RELATORIO_PRONTO = "relatorio_pronto"
TIPO_RELATORIO_LIVRE = "relatorio_livre"
TIPO_CODIGO_SQL = "codigo_sql"


class JobExtracao(Base):
    """
    Representa uma extração em andamento ou finalizada.

    A linha fica no banco até o cronjob de limpeza apagar (default: 1 dia
    depois do término). O arquivo CSV correspondente mora em
    `settings.pasta_jobs/{id}.csv` enquanto o job for retido.
    """
    __tablename__ = "jobs_extracao"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    usuario_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Também guardamos o username texto puro — se o usuário for deletado,
    # o histórico do job ainda faz sentido.
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # relatorio_pronto | relatorio_livre | codigo_sql
    tipo: Mapped[str] = mapped_column(String(30), nullable=False, index=True)

    # ID do relatório pronto (ct2010, qpr010, ...) ou "relatorio_livre" / "codigo_sql"
    # Usado tanto pra permissão quanto pra achar a mediana histórica no estimador.
    relatorio_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    # Rótulo pra exibir na listagem (ex: "CT2010 — 01/11 a 15/11").
    titulo: Mapped[str] = mapped_column(String(300), nullable=False)

    # Filtros que originaram o job (JSON). Também vira `parametros` no log.
    filtros_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # SQL do job de código SQL. None nos outros tipos.
    sql_texto: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Status + progresso estimado (0-100). O estimador cuida de atualizar esses.
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default=STATUS_PENDENTE, server_default=STATUS_PENDENTE, index=True
    )
    progresso_pct: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # Preenchidos quando o job termina (ou durante, pra tratar).
    total_linhas: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tamanho_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Caminho absoluto do CSV em disco quando concluido.
    caminho_csv: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Nome a usar no Content-Disposition do download (ex: "CT2010_20260101_a_20260131.csv").
    nome_arquivo: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    # Mensagem de erro quando status=erro (truncada a 2000 chars).
    erro_mensagem: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ETA estimado em segundos no momento do dispatch — usado pra barra de %.
    # None se não tiver histórico; o front mostra barra indeterminada.
    duracao_estimada_s: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    iniciado_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    concluido_em: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<JobExtracao id={self.id} tipo={self.tipo!r} status={self.status!r}>"
