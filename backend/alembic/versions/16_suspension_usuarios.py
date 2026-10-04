"""suspensión de usuarios: temporal (baneado_hasta) o permanente (activo=False)

Revision ID: suspension_usuarios
Revises: sugerencias_horarios_manuales
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "suspension_usuarios"
down_revision: Union[str, None] = "sugerencias_horarios_manuales"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("baneado_hasta", sa.DateTime(timezone=True)))
    op.add_column("usuarios", sa.Column("motivo_ban", sa.String(300)))


def downgrade() -> None:
    op.drop_column("usuarios", "motivo_ban")
    op.drop_column("usuarios", "baneado_hasta")
