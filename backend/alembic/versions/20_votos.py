"""votos de los usuarios sobre las respuestas del chat

Revision ID: votos
Revises: campus_completo
Create Date: 2026-10-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "votos"
down_revision: Union[str, None] = "campus_completo"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

motivo = postgresql.ENUM("NO_SIRVE", "INCORRECTO", name="motivovotoenum", create_type=False)


def upgrade() -> None:
    op.add_column("mensajes_chat", sa.Column("informacion_ids", sa.JSON()))
    op.add_column("informaciones", sa.Column("puntaje_votos", sa.Integer(), nullable=False, server_default="0"))
    motivo.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "votos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mensaje_id", sa.Integer(), sa.ForeignKey("mensajes_chat.id", ondelete="CASCADE"), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("valor", sa.Integer(), nullable=False),
        sa.Column("motivo", motivo),
        sa.Column("comentario", sa.String(500)),
        sa.Column("revisado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("revisor_id", sa.Integer(), sa.ForeignKey("usuarios.id")),
        sa.Column("resolucion", sa.String(300)),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("mensaje_id", "usuario_id", name="uq_voto_mensaje_usuario"),
    )
    op.create_index("ix_votos_mensaje_id", "votos", ["mensaje_id"])
    op.create_index("ix_votos_revisado", "votos", ["revisado"])


def downgrade() -> None:
    op.drop_table("votos")
    motivo.drop(op.get_bind(), checkfirst=True)
    op.drop_column("informaciones", "puntaje_votos")
    op.drop_column("mensajes_chat", "informacion_ids")
