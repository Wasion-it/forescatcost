"""fechamento individual de cada despesa, com fatura própria

Revision ID: f4b8d2c6a1e3
Revises: d2f7b4a9e1c6
Create Date: 2026-11-09 09:00:00

Cada item da despesa (imposto, taxa, frete, serviço) passa a ser fechado separadamente, conforme
a fatura chega, com o próprio número de fatura. O processo vira FECHADO quando o último item é
fechado.

Esquema:
- importacao_despesa ganha numero_fatura (texto até 60, obrigatório, não vazio) e fechado_por
  (FK para usuario); criado_em continua sendo o momento do fechamento do item;
- ck_importacao_fechamento deixa de exigir importacao.numero_fatura (o número fica em cada item).
  importacao.numero_fatura é mantida apenas para processos fechados antes desta mudança, que não
  têm itens detalhados.
Dados: os itens já fechados recebem o número da fatura e o responsável do processo.
Downgrade: itens fechados de processos ainda não totalmente fechados são removidos (o modelo
anterior só registrava itens no fechamento completo); processos FECHADO sem número no processo
recebem os números dos itens concatenados (até 60 caracteres).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4b8d2c6a1e3"
down_revision: str | Sequence[str] | None = "d2f7b4a9e1c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "importacao_despesa", sa.Column("numero_fatura", sa.String(length=60), nullable=True)
    )
    op.add_column("importacao_despesa", sa.Column("fechado_por", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE importacao_despesa d "
        "SET numero_fatura = coalesce(nullif(i.numero_fatura, ''), 'não informado'), "
        "    fechado_por = i.fechado_por "
        "FROM importacao i WHERE i.id = d.importacao_id"
    )
    op.alter_column("importacao_despesa", "numero_fatura", nullable=False)
    op.create_check_constraint(
        "ck_importacao_despesa_fatura", "importacao_despesa", "numero_fatura <> ''"
    )
    op.create_foreign_key(
        "importacao_despesa_fechado_por_fkey",
        "importacao_despesa",
        "usuario",
        ["fechado_por"],
        ["id"],
    )
    op.drop_constraint("ck_importacao_fechamento", "importacao", type_="check")
    op.create_check_constraint(
        "ck_importacao_fechamento",
        "importacao",
        "status <> 'FECHADO' OR (valor_fatura IS NOT NULL AND valor_fatura > 0)",
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM importacao_despesa d USING importacao i "
        "WHERE i.id = d.importacao_id AND i.status <> 'FECHADO'"
    )
    op.execute(
        "UPDATE importacao i SET numero_fatura = left(sub.numeros, 60) "
        "FROM (SELECT importacao_id, string_agg(DISTINCT numero_fatura, ', ') AS numeros "
        "      FROM importacao_despesa GROUP BY importacao_id) sub "
        "WHERE sub.importacao_id = i.id AND i.status = 'FECHADO' "
        "  AND (i.numero_fatura IS NULL OR i.numero_fatura = '')"
    )
    op.drop_constraint("ck_importacao_fechamento", "importacao", type_="check")
    op.create_check_constraint(
        "ck_importacao_fechamento",
        "importacao",
        "status <> 'FECHADO' OR (valor_fatura IS NOT NULL AND valor_fatura > 0 "
        "AND numero_fatura IS NOT NULL AND numero_fatura <> '')",
    )
    op.drop_constraint(
        "importacao_despesa_fechado_por_fkey", "importacao_despesa", type_="foreignkey"
    )
    op.drop_constraint("ck_importacao_despesa_fatura", "importacao_despesa", type_="check")
    op.drop_column("importacao_despesa", "fechado_por")
    op.drop_column("importacao_despesa", "numero_fatura")
