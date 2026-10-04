"""códigos de verificación por mail: registro público y recuperación de contraseña

Revision ID: codigos_verificacion
Revises: busqueda_sin_tildes
Create Date: 2026-10-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "codigos_verificacion"
down_revision: Union[str, None] = "busqueda_sin_tildes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

proposito = postgresql.ENUM("REGISTRO", "RECUPERACION", name="propositocodigoenum", create_type=False)


def upgrade() -> None:
    proposito.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "codigos_verificacion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("proposito", proposito, nullable=False),
        sa.Column("codigo_hash", sa.String(64), nullable=False),
        sa.Column("datos", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("intentos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("usado", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("expira_en", sa.DateTime(timezone=True), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_codigos_verificacion_email", "codigos_verificacion", ["email"])


def downgrade() -> None:
    op.drop_table("codigos_verificacion")
    proposito.drop(op.get_bind(), checkfirst=True)
