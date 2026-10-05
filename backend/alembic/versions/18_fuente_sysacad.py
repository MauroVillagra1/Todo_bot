"""fuente: avisos públicos del ingreso al SYSACAD (inscripciones, certificados, contactos)

Revision ID: fuente_sysacad
Revises: fuente_campus_virtual
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "fuente_sysacad"
down_revision: Union[str, None] = "fuente_campus_virtual"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO fuentes (nombre, tipo, url, confiabilidad_base, activa, config)
        VALUES ('SYSACAD FRT (avisos)', 'WEB', 'https://sysacad.frt.utn.edu.ar', 100, true,
                '{"cada_horas": 6, "paginas": [{"url": "https://sysacad.frt.utn.edu.ar/loginAlumno.asp",
                  "titulo": "SYSACAD (autogestión de alumnos): avisos importantes",
                  "desde": "Inicio de sesión", "hasta": "En caso de error"}]}'::jsonb)
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM fuentes WHERE url = 'https://sysacad.frt.utn.edu.ar'")
