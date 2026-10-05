"""búsqueda aproximada: "becsa" encuentra "becas" (pg_trgm)

Revision ID: busqueda_aproximada
Revises: votos
Create Date: 2026-10-05

Última pasada de la búsqueda (app/rag/search.py): palabras parecidas por trigramas.
Si la extensión no está (Postgres embebido de desarrollo), esa pasada se saltea.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "busqueda_aproximada"
down_revision: Union[str, None] = "votos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    hay_trgm = op.get_bind().exec_driver_sql(
        "SELECT 1 FROM pg_available_extensions WHERE name = 'pg_trgm'").first()
    if hay_trgm:
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
