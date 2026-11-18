"""jobs_extracao

Revision ID: 0003_jobs
Revises: 0002_areas
Create Date: 2026-11-18

Tabela de jobs de extração assíncrona (Etapa 11).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0003_jobs"
down_revision: Union[str, None] = "0002_areas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jobs_extracao",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("relatorio_id", sa.String(100), nullable=False),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("filtros_json", JSONB, nullable=True),
        sa.Column("sql_texto", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="pendente",
        ),
        sa.Column(
            "progresso_pct",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("total_linhas", sa.Integer(), nullable=True),
        sa.Column("tamanho_bytes", sa.BigInteger(), nullable=True),
        sa.Column("caminho_csv", sa.String(500), nullable=True),
        sa.Column("nome_arquivo", sa.String(300), nullable=True),
        sa.Column("erro_mensagem", sa.Text(), nullable=True),
        sa.Column("duracao_estimada_s", sa.Integer(), nullable=True),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("iniciado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_index("ix_jobs_extracao_usuario_id", "jobs_extracao", ["usuario_id"])
    op.create_index("ix_jobs_extracao_tipo", "jobs_extracao", ["tipo"])
    op.create_index("ix_jobs_extracao_relatorio_id", "jobs_extracao", ["relatorio_id"])
    op.create_index("ix_jobs_extracao_status", "jobs_extracao", ["status"])
    op.create_index("ix_jobs_extracao_criado_em", "jobs_extracao", ["criado_em"])


def downgrade() -> None:
    op.drop_table("jobs_extracao")
