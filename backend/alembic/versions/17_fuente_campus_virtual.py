"""fuente: catálogo público del Campus Virtual FRT (Moodle), aulas de Sistemas 2026

Revision ID: fuente_campus_virtual
Revises: suspension_usuarios
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "fuente_campus_virtual"
down_revision: Union[str, None] = "suspension_usuarios"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO fuentes (nombre, tipo, url, confiabilidad_base, activa, config)
        VALUES ('Campus Virtual FRT', 'WEB', 'https://frt.cvg.utn.edu.ar', 100, true,
                '{"moodle": true, "categoria": "Ingeniería en Sistemas de Información",
                  "solo": "2026", "cada_horas": 24}'::jsonb)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM fuentes WHERE url = 'https://frt.cvg.utn.edu.ar'")
