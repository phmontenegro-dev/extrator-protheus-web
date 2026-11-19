"""agendamentos e agendamentos_execucoes

Revision ID: 0004_agendamentos
Revises: 0003_jobs
Create Date: 2026-11-19

Tabelas da Etapa 14 — agendamento recorrente de relatórios.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0004_agendamentos"
down_revision: Union[str, None] = "0003_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agendamentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("nome", sa.String(100), nullable=False),
        sa.Column("descricao", sa.String(500), nullable=True),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("relatorio_id", sa.String(100), nullable=False),
        sa.Column("filtros_base", JSONB, nullable=True),
        sa.Column("sql_texto", sa.Text(), nullable=True),
        sa.Column("preset_datas", sa.String(40), nullable=True),
        sa.Column("frequencia", sa.String(20), nullable=False),
        sa.Column("dias_semana", JSONB, nullable=True),
        sa.Column("dia_mes", sa.Integer(), nullable=True),
        sa.Column("hora", sa.Integer(), nullable=False),
        sa.Column("minuto", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("proxima_execucao", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultima_execucao", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estrategia_nome", sa.String(20), nullable=False, server_default="padrao"),
        sa.Column("retencao_dias", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("token_hash", sa.String(100), nullable=True),
        sa.Column("token_prefixo", sa.String(20), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agendamentos_usuario_id", "agendamentos", ["usuario_id"])
    op.create_index("ix_agendamentos_relatorio_id", "agendamentos", ["relatorio_id"])
    op.create_index("ix_agendamentos_ativo", "agendamentos", ["ativo"])
    op.create_index("ix_agendamentos_proxima_execucao", "agendamentos", ["proxima_execucao"])

    op.create_table(
        "agendamentos_execucoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "agendamento_id",
            sa.Integer(),
            sa.ForeignKey("agendamentos.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "job_id",
            sa.String(36),
            sa.ForeignKey("jobs_extracao.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(20), nullable=False, server_default="pendente"),
        sa.Column("params_resolvidos", JSONB, nullable=True),
        sa.Column("total_linhas", sa.Integer(), nullable=True),
        sa.Column("tamanho_bytes", sa.Integer(), nullable=True),
        sa.Column("nome_arquivo", sa.String(300), nullable=True),
        sa.Column("erro_mensagem", sa.Text(), nullable=True),
        sa.Column("baixada_por", JSONB, nullable=True, server_default="[]"),
        sa.Column("criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("concluido_em", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agendamentos_execucoes_agendamento_id", "agendamentos_execucoes", ["agendamento_id"])
    op.create_index("ix_agendamentos_execucoes_job_id", "agendamentos_execucoes", ["job_id"])
    op.create_index("ix_agendamentos_execucoes_status", "agendamentos_execucoes", ["status"])
    op.create_index("ix_agendamentos_execucoes_criado_em", "agendamentos_execucoes", ["criado_em"])


def downgrade() -> None:
    op.drop_table("agendamentos_execucoes")
    op.drop_table("agendamentos")
