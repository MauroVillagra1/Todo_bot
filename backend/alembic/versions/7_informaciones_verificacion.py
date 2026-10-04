"""informaciones, evidencias, verificaciones e historial

Revision ID: informaciones
Revises: sistemas_sin_tp_event
Create Date: 2026-10-03
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "informaciones"
down_revision: Union[str, None] = "sistemas_sin_tp_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

tipo_info = postgresql.ENUM(
    "INSCRIPCION", "EXAMEN", "CALENDARIO", "BECA", "CONVOCATORIA", "EVENTO", "AVISO",
    "TRAMITE", "NOTICIA", "OTRO", name="tipoinformacionenum", create_type=False,
)
estado_info = postgresql.ENUM(
    "CONFIRMADA", "PROBABLE", "NO_CONFIRMADA", "CONTRADICTORIA", "DESACTUALIZADA",
    "REEMPLAZADA", name="estadoinformacionenum", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    tipo_info.create(bind, checkfirst=True)
    estado_info.create(bind, checkfirst=True)

    op.create_table(
        "informaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tipo", tipo_info, nullable=False),
        sa.Column("titulo", sa.String(500), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("fecha_inicio", sa.Date()),
        sa.Column("fecha_fin", sa.Date()),
        sa.Column("estado", estado_info, nullable=False),
        sa.Column("confianza", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_informaciones_tipo", "informaciones", ["tipo"])
    op.create_index("ix_informaciones_estado", "informaciones", ["estado"])
    op.create_index("ix_informaciones_fecha_fin", "informaciones", ["fecha_fin"])

    op.create_table(
        "evidencias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("informacion_id", sa.Integer(),
                  sa.ForeignKey("informaciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fuente_id", sa.Integer(), sa.ForeignKey("fuentes.id"), nullable=False),
        sa.Column("documento_id", sa.Integer(), sa.ForeignKey("documentos.id")),
        sa.Column("publicacion_id", sa.Integer(), sa.ForeignKey("publicaciones.id")),
        sa.Column("tipo_de_evidencia", sa.String(20), nullable=False),
    )
    op.create_index("ix_evidencias_informacion_id", "evidencias", ["informacion_id"])
    op.create_index("ix_evidencias_documento_id", "evidencias", ["documento_id"])
    op.create_index("ix_evidencias_publicacion_id", "evidencias", ["publicacion_id"])

    op.create_table(
        "verificaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("informacion_id", sa.Integer(),
                  sa.ForeignKey("informaciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resultado", estado_info, nullable=False),
        sa.Column("puntuacion", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("explicacion", sa.Text(), nullable=False),
    )
    op.create_index("ix_verificaciones_informacion_id", "verificaciones", ["informacion_id"])

    op.create_table(
        "historial",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("informacion_id", sa.Integer(),
                  sa.ForeignKey("informaciones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("contenido_anterior", sa.Text()),
        sa.Column("contenido_nuevo", sa.Text(), nullable=False),
        sa.Column("motivo", sa.String(200), nullable=False),
        sa.Column("fecha", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_historial_informacion_id", "historial", ["informacion_id"])


def downgrade() -> None:
    for tabla in ("historial", "verificaciones", "evidencias", "informaciones"):
        op.drop_table(tabla)
    bind = op.get_bind()
    estado_info.drop(bind, checkfirst=True)
    tipo_info.drop(bind, checkfirst=True)
