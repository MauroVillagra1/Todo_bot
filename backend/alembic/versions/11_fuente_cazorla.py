"""fuente no oficial: cazorla.com.ar (fechas de mesas, 40 %)

Revision ID: fuente_cazorla
Revises: horarios_clases
Create Date: 2026-10-04

Su robots.txt pide no rastrear /argentina/ ("Disallow: /"), así que no se lee
automáticamente: es de carga manual (MOD) hasta que el dueño lo autorice.
Con 40 % de confiabilidad su información queda NO_CONFIRMADA.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "fuente_cazorla"
down_revision: Union[str, None] = "horarios_clases"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO fuentes (nombre, tipo, url, confiabilidad_base, activa, config)
        VALUES ('Mesas 2026 (cazorla.com.ar, no oficial)', 'MANUAL', 'https://cazorla.com.ar/argentina/',
                40, true, '{"nota": "robots.txt no permite rastreo automático: carga manual"}'::jsonb)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM fuentes WHERE url = 'https://cazorla.com.ar/argentina/'")
