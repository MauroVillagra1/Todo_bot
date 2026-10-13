"""sesiones seguras: versión de sesión (revocar JWT) y bloqueo por intentos fallidos

Revision ID: sesiones_seguras
Revises: busqueda_semantica
Create Date: 2026-10-13

usuarios.version_sesion va en cada token (core/tokens.py): subirla invalida los tokens viejos.
usuarios.intentos_fallidos / bloqueado_hasta: el login se bloquea un rato tras varios errores.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "sesiones_seguras"
down_revision: Union[str, None] = "busqueda_semantica"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("version_sesion", sa.Integer(), server_default="0", nullable=False))
    op.add_column("usuarios", sa.Column("intentos_fallidos", sa.Integer(), server_default="0", nullable=False))
    op.add_column("usuarios", sa.Column("bloqueado_hasta", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("usuarios", "bloqueado_hasta")
    op.drop_column("usuarios", "intentos_fallidos")
    op.drop_column("usuarios", "version_sesion")
