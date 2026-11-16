"""initial — usuarios, permissoes_relatorio, logs_acesso, sessoes

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============= usuarios =============
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("nome_completo", sa.String(200), nullable=False),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("senha_hash", sa.String(255), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ultimo_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_usuarios_username", "usuarios", ["username"])

    # ============= permissoes_relatorio =============
    op.create_table(
        "permissoes_relatorio",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relatorio_id", sa.String(100), nullable=False),
        sa.Column(
            "concedido_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "concedido_por_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.UniqueConstraint("usuario_id", "relatorio_id", name="uq_usuario_relatorio"),
    )
    op.create_index("ix_permissoes_usuario", "permissoes_relatorio", ["usuario_id"])
    op.create_index("ix_permissoes_relatorio", "permissoes_relatorio", ["relatorio_id"])

    # ============= logs_acesso =============
    op.create_table(
        "logs_acesso",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("acao", sa.String(50), nullable=False),
        sa.Column("relatorio_id", sa.String(100), nullable=True),
        sa.Column("parametros", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("registros_retornados", sa.Integer(), nullable=True),
        sa.Column("duracao_ms", sa.Integer(), nullable=True),
        sa.Column("ip_origem", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("sucesso", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("erro_mensagem", sa.Text(), nullable=True),
    )
    op.create_index("ix_logs_timestamp", "logs_acesso", ["timestamp"])
    op.create_index("ix_logs_username", "logs_acesso", ["username"])
    op.create_index("ix_logs_acao", "logs_acesso", ["acao"])
    op.create_index("ix_logs_relatorio", "logs_acesso", ["relatorio_id"])

    # ============= sessoes =============
    op.create_table(
        "sessoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("token", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "usuario_id",
            sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "criada_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_origem", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
    )
    op.create_index("ix_sessoes_token", "sessoes", ["token"])
    op.create_index("ix_sessoes_usuario", "sessoes", ["usuario_id"])


def downgrade() -> None:
    op.drop_table("sessoes")
    op.drop_table("logs_acesso")
    op.drop_table("permissoes_relatorio")
    op.drop_table("usuarios")
