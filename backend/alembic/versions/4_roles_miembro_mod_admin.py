"""roles MIEMBRO / MOD / ADMIN y emails en minúsculas

Revision ID: roles_mma
Revises: eliminar_academico
Create Date: 2026-10-03

Mapeo (análisis MVP §11):
  administrador                         → ADMIN
  administrativo, jefe_departamento     → MOD
  alumno, profesor, profesor_directivo  → MIEMBRO
"""
from typing import Sequence, Union

from alembic import op

revision: str = "roles_mma"
down_revision: Union[str, None] = "eliminar_academico"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE rolenum RENAME TO rolenum_old")
    op.execute("CREATE TYPE rolenum AS ENUM ('MIEMBRO', 'MOD', 'ADMIN')")
    op.execute(
        """
        ALTER TABLE usuarios ALTER COLUMN rol TYPE rolenum USING (
            CASE rol::text
                WHEN 'administrador'     THEN 'ADMIN'
                WHEN 'administrativo'    THEN 'MOD'
                WHEN 'jefe_departamento' THEN 'MOD'
                ELSE 'MIEMBRO'
            END
        )::rolenum
        """
    )
    op.execute("DROP TYPE rolenum_old")
    # El login compara en minúsculas
    op.execute("UPDATE usuarios SET email = lower(email)")


def downgrade() -> None:
    op.execute("ALTER TYPE rolenum RENAME TO rolenum_new")
    op.execute("CREATE TYPE rolenum AS ENUM ('administrador', 'profesor_directivo', 'alumno')")
    op.execute(
        """
        ALTER TABLE usuarios ALTER COLUMN rol TYPE rolenum USING (
            CASE rol::text WHEN 'ADMIN' THEN 'administrador' ELSE 'alumno' END
        )::rolenum
        """
    )
    op.execute("DROP TYPE rolenum_new")
