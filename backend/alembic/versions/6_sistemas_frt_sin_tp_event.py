"""Sistemas FRT: quitar tp_event (no está expuesto en la REST API)

Revision ID: sistemas_sin_tp_event
Revises: modelo_ingesta
Create Date: 2026-10-03

/wp-json/wp/v2/tp_event devuelve 404; /wp-json/wp/v2/types solo expone
posts y pages como contenido.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "sistemas_sin_tp_event"
down_revision: Union[str, None] = "modelo_ingesta"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE fuentes
        SET config = jsonb_set(config, '{tipos}', '["posts", "pages"]'::jsonb)
        WHERE nombre = 'Sistemas FRT'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE fuentes
        SET config = jsonb_set(config, '{tipos}', '["posts", "pages", "tp_event"]'::jsonb)
        WHERE nombre = 'Sistemas FRT'
        """
    )
