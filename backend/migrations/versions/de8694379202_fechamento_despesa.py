"""fechamento da despesa por processo

Revision ID: de8694379202
Revises: 6be361b0acc2
Create Date: 2026-10-15 08:18:52.196424

Esquema (tabela importacao):
- novo status FECHADO (a coluna status é texto; não há enum a alterar);
- colunas valor_fatura, numero_fatura, fechado_em e fechado_por (FK para usuario), todas nulas;
- constraint ck_importacao_fechamento: processo FECHADO exige fatura com valor > 0 e número
  preenchido.
Sem trigger novo: importacao já é auditada pela função genérica fn_auditoria.
Downgrade: remove constraint, FK e colunas. Processos FECHADO voltam para CALCULADO antes da
remoção (os dados da fatura são descartados).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "de8694379202"
down_revision: str | Sequence[str] | None = "6be361b0acc2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("importacao", sa.Column("valor_fatura", sa.Numeric(18, 2), nullable=True))
    op.add_column("importacao", sa.Column("numero_fatura", sa.String(length=60), nullable=True))
    op.add_column(
        "importacao", sa.Column("fechado_em", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("importacao", sa.Column("fechado_por", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "importacao_fechado_por_fkey", "importacao", "usuario", ["fechado_por"], ["id"]
    )
    op.create_check_constraint(
        "ck_importacao_fechamento",
        "importacao",
        "status <> 'FECHADO' OR (valor_fatura IS NOT NULL AND valor_fatura > 0 "
        "AND numero_fatura IS NOT NULL AND numero_fatura <> '')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_importacao_fechamento", "importacao", type_="check")
    op.execute("UPDATE importacao SET status = 'CALCULADO' WHERE status = 'FECHADO'")
    op.drop_constraint("importacao_fechado_por_fkey", "importacao", type_="foreignkey")
    op.drop_column("importacao", "fechado_por")
    op.drop_column("importacao", "fechado_em")
    op.drop_column("importacao", "numero_fatura")
    op.drop_column("importacao", "valor_fatura")
