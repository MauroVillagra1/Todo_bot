"""mesas de examen, calendario académico, documentos importantes e historial de chat

Revision ID: mesas_calendario_documentos
Revises: sesiones_seguras
Create Date: 2026-10-28

- mesas_fechas / mesas_materias: turnos de exámenes finales (Res. 2394/2025) y tribunales de I.S.I.
- calendario_eventos: calendario académico 2026 (Anexo I) y feriados/asuetos (Anexo II).
- documentos_importantes: notas y formularios para descargar (el archivo va en la base, ≤ 2 MB).
- mensajes_chat.datos: estado y fuentes de cada respuesta, para reabrir conversaciones.
- horarios_clases.anio vacío (PDFs del Anexo Concepción sin comisión): se toma del nombre del PDF.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.ingest.datos_calendario import eventos_iniciales
from app.ingest.datos_mesas import FECHAS_2026, materias_iniciales

revision: str = "mesas_calendario_documentos"
down_revision: Union[str, None] = "sesiones_seguras"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    fechas = op.create_table(
        "mesas_fechas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mesa", sa.Integer(), nullable=False, index=True),
        sa.Column("turno", sa.Integer()),
        sa.Column("cierre_inscripcion", sa.Date(), nullable=False),
        sa.Column("fecha_examen", sa.Date(), nullable=False, index=True),
    )
    materias = op.create_table(
        "mesas_materias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("materia", sa.String(200), nullable=False),
        sa.Column("materia_norm", sa.String(200), nullable=False, index=True),
        sa.Column("mesa", sa.Integer(), nullable=False),
        sa.Column("sede", sa.String(40), nullable=False),
        sa.Column("presidente", sa.String(120)),
        sa.Column("vocal1", sa.String(120)),
        sa.Column("vocal2", sa.String(120)),
        sa.Column("hora", sa.String(5)),
        sa.Column("anio_tribunal", sa.Integer()),
    )
    eventos = op.create_table(
        "calendario_eventos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fecha_inicio", sa.Date(), nullable=False, index=True),
        sa.Column("fecha_fin", sa.Date()),
        sa.Column("actividad", sa.String(300), nullable=False),
        sa.Column("categoria", sa.String(20), nullable=False),
        sa.Column("detalle", sa.String(300)),
    )
    op.create_table(
        "documentos_importantes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("archivo_nombre", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("contenido", sa.LargeBinary(), nullable=False),
        sa.Column("texto_extraido", sa.Text()),
        sa.Column("subido_por", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL")),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("mensajes_chat", sa.Column("datos", sa.JSON()))

    op.bulk_insert(fechas, FECHAS_2026)
    op.bulk_insert(materias, materias_iniciales())
    op.bulk_insert(eventos, eventos_iniciales())

    # "HORARIO ANEXO 3 AÑO – PLAN 2023": el año está en el nombre del PDF
    op.execute(
        r"""
        UPDATE horarios_clases h
        SET anio = CAST(substring(upper(d.nombre) from '(\d)\s*[°º]?\s*A[ÑN]O') AS integer)
        FROM documentos d
        WHERE h.documento_id = d.id AND h.anio IS NULL AND upper(d.nombre) ~ '\d\s*[°º]?\s*A[ÑN]O'
        """
    )


def downgrade() -> None:
    op.drop_column("mensajes_chat", "datos")
    op.drop_table("documentos_importantes")
    op.drop_table("calendario_eventos")
    op.drop_table("mesas_materias")
    op.drop_table("mesas_fechas")
