"""eliminar módulos académicos y persistir historial de chat

Revision ID: eliminar_academico
Revises: fix_excepciones_fecha
Create Date: 2026-10-03

Borra materias, comisiones, cursadas, eventos y materiales (decisión del
análisis MVP, §15). Antes de aplicarla se exportó un backup JSON de todas
las tablas fuera del repo.

Migración irreversible: el downgrade no recrea los datos borrados.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "eliminar_academico"
down_revision: Union[str, None] = "fix_excepciones_fecha"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Orden: primero las tablas que referencian a otras
_TABLAS_ACADEMICAS = [
    "materiales_apoyo",
    "eventos_calendario",
    "cursada_profesor",
    "cursada_excepciones",
    "usuario_comision",
    "info_cursada",
    "cursadas",
    "comisiones",
    "periodos_academicos",
    "materias",
]

_ENUMS_ACADEMICOS = [
    "alcanceeventoenum",
    "duracionenum",
    "modalidadenum",
    "tipoeventoenum",
    "tipoexcepcionenum",
    "tipomaterialenum",
    "tipoperiodoenum",
]


def upgrade() -> None:
    for tabla in _TABLAS_ACADEMICAS:
        op.execute(f'DROP TABLE IF EXISTS "{tabla}" CASCADE')
    for enum in _ENUMS_ACADEMICOS:
        op.execute(f'DROP TYPE IF EXISTS "{enum}"')

    op.create_table(
        "mensajes_chat",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("conversacion_id", sa.String(length=36), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("rol", sa.String(length=10), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column(
            "creado_en",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_mensajes_chat_conversacion_id"), "mensajes_chat", ["conversacion_id"]
    )
    op.create_index(
        "ix_mensajes_chat_usuario_fecha", "mensajes_chat", ["usuario_id", "creado_en"]
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Migración irreversible: restaurar los módulos académicos desde el backup JSON."
    )
