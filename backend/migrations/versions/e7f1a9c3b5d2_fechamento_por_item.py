"""fechamento da despesa item a item

Revision ID: e7f1a9c3b5d2
Revises: d5e9f3a2b8c4
Create Date: 2026-10-16 09:00:00

Esquema:
- tabela importacao_despesa: valor realizado de cada item do cálculo (calculo_item), informado
  ao fechar o processo; um registro por item e por processo; valor >= 0;
- trigger de auditoria na nova tabela (mesma função genérica fn_auditoria).
importacao.valor_fatura passa a ser a soma dos itens. Processos já fechados continuam com o total
da fatura e sem itens detalhados.
Downgrade: remove a tabela (os valores por item são descartados; o total permanece).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7f1a9c3b5d2"
down_revision: str | Sequence[str] | None = "d5e9f3a2b8c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "importacao_despesa",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("importacao_id", sa.Uuid(), nullable=False),
        sa.Column("calculo_item_id", sa.Uuid(), nullable=False),
        sa.Column("valor", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("valor >= 0", name="ck_importacao_despesa_valor"),
        sa.ForeignKeyConstraint(["importacao_id"], ["importacao.id"]),
        sa.ForeignKeyConstraint(["calculo_item_id"], ["calculo_item.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("importacao_id", "calculo_item_id"),
    )
    op.execute(
        "CREATE TRIGGER trg_auditoria_importacao_despesa "
        "AFTER INSERT OR UPDATE OR DELETE ON importacao_despesa "
        "FOR EACH ROW EXECUTE FUNCTION fn_auditoria()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_auditoria_importacao_despesa ON importacao_despesa")
    op.drop_table("importacao_despesa")
