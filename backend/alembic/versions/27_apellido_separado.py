"""usuarios: apellido por separado (Mi perfil edita nombre y apellido en campos distintos)

Revision ID: apellido_separado
Revises: roles_smod_historial
Create Date: 2026-10-28

Las cuentas existentes quedan sin apellido: se separa la primera palabra como nombre
(Usuario.partes_del_nombre) hasta que la persona guarde su perfil.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "apellido_separado"
down_revision: Union[str, None] = "roles_smod_historial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("usuarios", sa.Column("apellido", sa.String(74)))


def downgrade() -> None:
    op.drop_column("usuarios", "apellido")
