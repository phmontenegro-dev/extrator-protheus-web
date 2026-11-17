"""areas e relatorio_areas

Revision ID: 0002_areas
Revises: 0001_initial
Create Date: 2026-11-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_areas"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nome", sa.String(100), nullable=False, unique=True),
        sa.Column("descricao", sa.String(500), nullable=True),
        sa.Column("ordem", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_areas_ordem", "areas", ["ordem"])

    op.create_table(
        "relatorio_areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("relatorio_id", sa.String(100), nullable=False, unique=True),
        sa.Column(
            "area_id",
            sa.Integer(),
            sa.ForeignKey("areas.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_relatorio_areas_area", "relatorio_areas", ["area_id"])


def downgrade() -> None:
    op.drop_table("relatorio_areas")
    op.drop_table("areas")
