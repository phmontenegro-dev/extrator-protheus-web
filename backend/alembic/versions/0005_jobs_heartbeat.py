"""jobs_extracao.heartbeat_em

Revision ID: 0005_jobs_heartbeat
Revises: 0004_agendamentos
Create Date: 2026-11-19

Adiciona coluna heartbeat_em usada pelo watchdog do scheduler pra detectar
jobs zumbis (worker morreu sem marcar status final). A thread de progresso
atualiza esse campo a cada 2s; o watchdog marca como erro qualquer job em
status ativo com heartbeat_em < now() - 60s.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_jobs_heartbeat"
down_revision: Union[str, None] = "0004_agendamentos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "jobs_extracao",
        sa.Column("heartbeat_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_jobs_extracao_heartbeat_em", "jobs_extracao", ["heartbeat_em"]
    )


def downgrade() -> None:
    op.drop_index("ix_jobs_extracao_heartbeat_em", table_name="jobs_extracao")
    op.drop_column("jobs_extracao", "heartbeat_em")
