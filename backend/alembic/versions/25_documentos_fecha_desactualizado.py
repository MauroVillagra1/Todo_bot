"""documentos importantes: fecha del documento y marca de desactualizado

Revision ID: documentos_fecha_desactualizado
Revises: mesas_calendario_documentos
Create Date: 2026-10-28
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "documentos_fecha_desactualizado"
down_revision: Union[str, None] = "mesas_calendario_documentos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documentos_importantes", sa.Column("fecha_documento", sa.Date()))
    op.add_column("documentos_importantes",
                  sa.Column("desactualizado", sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column("documentos_importantes", "desactualizado")
    op.drop_column("documentos_importantes", "fecha_documento")
