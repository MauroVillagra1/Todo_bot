"""sugerencias de usuarios y bloques de horario cargados a mano por un ADMIN

Revision ID: sugerencias_horarios_manuales
Revises: codigos_verificacion
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "sugerencias_horarios_manuales"
down_revision: Union[str, None] = "codigos_verificacion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

estado = postgresql.ENUM("PENDIENTE", "ACEPTADA", "RECHAZADA", name="estadosugerenciaenum", create_type=False)


def upgrade() -> None:
    estado.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "sugerencias",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id"), nullable=False),
        sa.Column("titulo", sa.String(300), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("url", sa.String(1000)),
        sa.Column("estado", estado, nullable=False, server_default="PENDIENTE"),
        sa.Column("revisor_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("motivo", sa.String(500)),
        sa.Column("publicacion_id", sa.Integer(), sa.ForeignKey("publicaciones.id")),
        sa.Column("creada_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revisada_en", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_sugerencias_usuario_id", "sugerencias", ["usuario_id"])
    op.create_index("ix_sugerencias_estado", "sugerencias", ["estado"])

    # Bloques agregados desde el panel: sin PDF de origen
    op.alter_column("horarios_clases", "documento_id", nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM horarios_clases WHERE documento_id IS NULL")
    op.alter_column("horarios_clases", "documento_id", nullable=False)
    op.drop_table("sugerencias")
    estado.drop(op.get_bind(), checkfirst=True)
