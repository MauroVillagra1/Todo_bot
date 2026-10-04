"""fix cursada_excepciones: reemplaza fecha_inicio/fecha_fin por fecha

Revision ID: fix_excepciones_fecha
Revises: d34030ed69f9
Create Date: 2026-08-27

El modelo fue refactorizado para manejar excepciones de UN SOLO DÍA.
La BD tenía fecha_inicio + fecha_fin; el modelo actual usa solo fecha.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "fix_excepciones_fecha"
down_revision: Union[str, None] = "d34030ed69f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agregar la nueva columna fecha (nullable primero para no romper filas existentes)
    op.add_column(
        "cursada_excepciones",
        sa.Column("fecha", sa.Date(), nullable=True),
    )

    # 2. Poblar fecha con fecha_inicio para las filas existentes
    op.execute("UPDATE cursada_excepciones SET fecha = fecha_inicio")

    # 3. Hacer la columna NOT NULL ahora que tiene datos
    op.alter_column("cursada_excepciones", "fecha", nullable=False)

    # 4. Crear índice igual al que define el modelo
    op.create_index(
        op.f("ix_cursada_excepciones_fecha"),
        "cursada_excepciones",
        ["fecha"],
        unique=False,
    )

    # 5. Eliminar las columnas viejas
    op.drop_column("cursada_excepciones", "fecha_inicio")
    op.drop_column("cursada_excepciones", "fecha_fin")


def downgrade() -> None:
    # Restaurar columnas antiguas
    op.add_column(
        "cursada_excepciones",
        sa.Column("fecha_inicio", sa.Date(), nullable=True),
    )
    op.add_column(
        "cursada_excepciones",
        sa.Column("fecha_fin", sa.Date(), nullable=True),
    )

    # Poblar desde fecha
    op.execute("UPDATE cursada_excepciones SET fecha_inicio = fecha, fecha_fin = fecha")

    op.alter_column("cursada_excepciones", "fecha_inicio", nullable=False)
    op.alter_column("cursada_excepciones", "fecha_fin", nullable=False)

    # Eliminar índice y columna nueva
    op.drop_index(op.f("ix_cursada_excepciones_fecha"), table_name="cursada_excepciones")
    op.drop_column("cursada_excepciones", "fecha")
