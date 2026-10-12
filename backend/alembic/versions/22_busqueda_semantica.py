"""búsqueda semántica: chunks.embedding (pgvector)

Revision ID: busqueda_semantica
Revises: busqueda_aproximada
Create Date: 2026-10-12

Vector de significado de cada chunk (services/embeddings.py). halfvec(768) = 1,5 KB por
chunk; sin índice: con unos miles de chunks la búsqueda exacta es rápida y no ocupa más.
Si la extensión no está (Postgres embebido de desarrollo), la búsqueda sigue solo por palabras.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "busqueda_semantica"
down_revision: Union[str, None] = "busqueda_aproximada"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    hay_vector = op.get_bind().exec_driver_sql(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'vector'").first()
    if hay_vector:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute("ALTER TABLE chunks ADD COLUMN IF NOT EXISTS embedding halfvec(768)")


def downgrade() -> None:
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS embedding")
