"""número da invoice no processo

Revision ID: d2f7b4a9e1c6
Revises: c1e4a7d9b3f5
Create Date: 2026-10-20 09:00:00

Esquema: importacao.numero_invoice (texto de até 60 caracteres, opcional, sem unicidade: a mesma
invoice pode aparecer em mais de um processo, por exemplo em embarques parciais).
Sem dados a migrar.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2f7b4a9e1c6"
down_revision: str | Sequence[str] | None = "c1e4a7d9b3f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("importacao", sa.Column("numero_invoice", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("importacao", "numero_invoice")
