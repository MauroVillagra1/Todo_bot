"""sugerencias: estado BORRADA (un SMOD o ADMIN saca del chat una sugerencia aceptada)

Revision ID: sugerencias_borradas
Revises: apellido_separado
Create Date: 2026-10-28
"""
from typing import Sequence, Union

from alembic import op

revision: str = "sugerencias_borradas"
down_revision: Union[str, None] = "apellido_separado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE no puede usarse en la misma transacción en la que se crea
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE estadosugerenciaenum ADD VALUE IF NOT EXISTS 'BORRADA'")


def downgrade() -> None:
    # Postgres no quita valores de un enum: las borradas vuelven a figurar como rechazadas
    op.execute("UPDATE sugerencias SET estado = 'RECHAZADA' WHERE estado = 'BORRADA'")
