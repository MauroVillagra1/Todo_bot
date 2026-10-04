"""Instagram por Instaloader desde la PC local: activa las 4 cuentas

Revision ID: instagram_instaloader
Revises: fuente_cazorla
Create Date: 2026-10-04

Las lee scripts/instagram_local.ps1 al iniciar Windows. GitHub Actions las
excluye (Instagram bloquea IPs de datacenter).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "instagram_instaloader"
down_revision: Union[str, None] = "fuente_cazorla"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE fuentes SET activa = true, config = config || '{"instaloader": true}'::jsonb
        WHERE tipo = 'INSTAGRAM'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE fuentes SET activa = false, config = config - 'instaloader'
        WHERE tipo = 'INSTAGRAM'
        """
    )
