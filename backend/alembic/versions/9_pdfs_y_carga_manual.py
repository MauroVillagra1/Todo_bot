"""PDFs de Sistemas FRT y fuentes de Instagram/WhatsApp autorizadas

Revision ID: pdfs_manual
Revises: cache_respuestas
Create Date: 2026-10-04

- documentos.fecha_publicacion (fecha de subida en la fuente).
- Fuente "Sistemas FRT (PDFs)": biblioteca de medios de WordPress, separada de
  los posts para tener su propia marca de última revisión. Excluye CVs.
- Instagram y WhatsApp quedan activas para carga manual por MOD (autorizadas
  por sus dueños). Instagram además se lee por API si hay token configurado.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "pdfs_manual"
down_revision: Union[str, None] = "cache_respuestas"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONFIG_PDFS = (
    '{"api": "https://sistemasfrtutn.ar/wp-json/wp/v2", "tipos": [], "pdfs": true, '
    '"excluir_pdf": "(?i)(^|[-_ ])(cv|curriculum)"}'
)


def upgrade() -> None:
    op.add_column("documentos", sa.Column("fecha_publicacion", sa.DateTime(timezone=True)))
    op.execute(
        f"""
        INSERT INTO fuentes (nombre, tipo, url, confiabilidad_base, activa, config)
        VALUES ('Sistemas FRT (PDFs)', 'WORDPRESS', 'https://sistemasfrtutn.ar', 100, true,
                '{_CONFIG_PDFS}'::jsonb)
        """
    )
    op.execute("UPDATE fuentes SET activa = true WHERE tipo IN ('INSTAGRAM', 'WHATSAPP')")


def downgrade() -> None:
    op.execute("UPDATE fuentes SET activa = false WHERE tipo IN ('INSTAGRAM', 'WHATSAPP')")
    op.execute("DELETE FROM fuentes WHERE nombre = 'Sistemas FRT (PDFs)'")
    op.drop_column("documentos", "fecha_publicacion")
