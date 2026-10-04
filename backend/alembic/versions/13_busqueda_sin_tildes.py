"""búsqueda sin tildes: "cuando" encuentra "cuándo"

Revision ID: busqueda_sin_tildes
Revises: instagram_instaloader
Create Date: 2026-10-04

El stemmer español de Postgres no quita acentos y casi nadie los escribe en el
chat. chunks.tsv pasa a indexar el texto sin tildes; la búsqueda hace lo mismo
con la pregunta. unaccent no es IMMUTABLE, por eso va envuelta en sin_tildes()
(requisito de las columnas generadas).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "busqueda_sin_tildes"
down_revision: Union[str, None] = "instagram_instaloader"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tsv(expresion: str) -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_tsv")
    op.execute("ALTER TABLE chunks DROP COLUMN tsv")
    op.execute(f"ALTER TABLE chunks ADD COLUMN tsv tsvector GENERATED ALWAYS AS ({expresion}) STORED")
    op.execute("CREATE INDEX ix_chunks_tsv ON chunks USING gin (tsv)")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sin_tildes(text) RETURNS text
        LANGUAGE sql IMMUTABLE PARALLEL SAFE STRICT
        AS $$ SELECT public.unaccent('public.unaccent'::regdictionary, $1) $$
        """
    )
    _tsv("to_tsvector('spanish', sin_tildes(texto))")


def downgrade() -> None:
    _tsv("to_tsvector('spanish', texto)")
    op.execute("DROP FUNCTION IF EXISTS sin_tildes(text)")
