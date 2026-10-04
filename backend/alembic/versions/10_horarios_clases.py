"""horarios estructurados (bloques de clase de las grillas en PDF)

Revision ID: horarios_clases
Revises: pdfs_manual
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "horarios_clases"
down_revision: Union[str, None] = "pdfs_manual"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "horarios_clases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("comision", sa.String(10)),
        sa.Column("anio", sa.Integer()),
        sa.Column("plan", sa.String(10)),
        sa.Column("turno", sa.String(30)),
        sa.Column("periodo", sa.String(40)),
        sa.Column("aula", sa.String(40)),
        sa.Column("dia", sa.Integer(), nullable=False),
        sa.Column("inicio", sa.String(5), nullable=False),
        sa.Column("fin", sa.String(5), nullable=False),
        sa.Column("materia", sa.String(200), nullable=False),
        sa.Column("materia_norm", sa.String(200), nullable=False),
        sa.Column("docente", sa.String(200)),
        sa.Column("lugar", sa.String(60)),
        sa.Column("electiva", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_horarios_clases_documento_id", "horarios_clases", ["documento_id"])
    op.create_index("ix_horarios_clases_comision", "horarios_clases", ["comision"])
    op.create_index("ix_horarios_clases_materia_norm", "horarios_clases", ["materia_norm"])


def downgrade() -> None:
    op.drop_table("horarios_clases")
