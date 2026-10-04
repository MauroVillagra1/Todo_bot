"""caché de respuestas del chat

Revision ID: cache_respuestas
Revises: informaciones
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "cache_respuestas"
down_revision: Union[str, None] = "informaciones"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cache_respuestas",
        sa.Column("clave", sa.String(64), primary_key=True),
        sa.Column("respuesta", postgresql.JSONB(), nullable=False),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_cache_respuestas_expira_en", "cache_respuestas", ["expira_en"])


def downgrade() -> None:
    op.drop_table("cache_respuestas")
