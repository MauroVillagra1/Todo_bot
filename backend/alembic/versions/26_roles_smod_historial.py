"""rol SMOD, docentes como MOD, deshacer cambios y documentos borrados recuperables

Revision ID: roles_smod_historial
Revises: documentos_fecha_desactualizado
Create Date: 2026-10-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "roles_smod_historial"
down_revision: Union[str, None] = "documentos_fecha_desactualizado"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE no puede usarse en la misma transacción en la que se crea
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE rolenum ADD VALUE IF NOT EXISTS 'SMOD' AFTER 'MOD'")
    op.execute("UPDATE usuarios SET rol = 'MOD' WHERE rol = 'MIEMBRO' AND email LIKE '%@doc.frt.utn.edu.ar'")
    op.add_column("registro_cambios", sa.Column("deshecho_por_id", sa.Integer()))
    op.add_column("documentos_importantes",
                  sa.Column("borrado", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("documentos_importantes", "borrado")
    op.drop_column("registro_cambios", "deshecho_por_id")
    op.execute("UPDATE usuarios SET rol = 'MOD' WHERE rol = 'SMOD'")  # Postgres no quita valores de un enum
