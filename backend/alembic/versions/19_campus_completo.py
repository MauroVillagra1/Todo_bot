"""Campus Virtual: todo el catálogo (todas las carreras, tecnicaturas y posgrados), no solo Sistemas

Revision ID: campus_completo
Revises: fuente_sysacad
Create Date: 2026-10-05
"""
from typing import Sequence, Union

from alembic import op

revision: str = "campus_completo"
down_revision: Union[str, None] = "fuente_sysacad"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Sin "categoria": recorre todo. ultima_revision en NULL para que la próxima corrida no espere 24 h
    op.execute("""
        UPDATE fuentes SET config = '{"moodle": true, "cada_horas": 24}'::jsonb, ultima_revision = NULL
        WHERE url = 'https://frt.cvg.utn.edu.ar'
    """)


def downgrade() -> None:
    op.execute("""
        UPDATE fuentes SET config = '{"moodle": true, "categoria": "Ingeniería en Sistemas de Información",
                                       "solo": "2026", "cada_horas": 24}'::jsonb
        WHERE url = 'https://frt.cvg.utn.edu.ar'
    """)
