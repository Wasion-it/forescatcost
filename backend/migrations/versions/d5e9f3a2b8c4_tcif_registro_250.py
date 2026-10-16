"""TCIF: valor por PLI passa de R$ 245,00 para R$ 250,00

Revision ID: d5e9f3a2b8c4
Revises: c4d8e2f1a7b3
Create Date: 2026-10-15 17:00:00

Só dados. Roda apenas quando o banco já está populado; em banco novo o seed já usa 250.

O valor de R$ 245,00 veio do levantamento inicial e não tem respaldo na legislação. A Lei
13.451/2017, art. 8º, § 2º, fixa R$ 250,00 por pedido de licenciamento de importação e
R$ 45,00 por mercadoria (cada parcela limitada a 1,5%).

- encerra a vigência em aberto do valor padrão de tcif_valor_ip na véspera e cria a nova,
  a partir da data da migração (cálculos já registrados não mudam);
- processos CALCULADOS ficam marcados com recálculo pendente.

Downgrade: remove a vigência criada aqui e reabre a anterior.
"""

from collections.abc import Sequence
from datetime import timedelta

import sqlalchemy as sa
from alembic import op

revision: str = "d5e9f3a2b8c4"
down_revision: str | Sequence[str] | None = "c4d8e2f1a7b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CHAVE = "tcif_valor_ip"
JUSTIFICATIVA = (
    "Lei 13.451/2017, art. 8º, § 2º: R$ 250,00 por PLI (antes 245,00, sem respaldo legal)"
)


def upgrade() -> None:
    conn = op.get_bind()
    parametro_id = conn.execute(
        sa.text("SELECT id FROM parametro WHERE chave = :chave"), {"chave": CHAVE}
    ).scalar()
    if parametro_id is None:
        return
    ja_aplicada = conn.execute(
        sa.text(
            "SELECT 1 FROM parametro_valor WHERE parametro_id = :p AND escopo_ref_id IS NULL "
            "AND vigencia_fim IS NULL AND valor = 250"
        ),
        {"p": parametro_id},
    ).first()
    if ja_aplicada:
        return
    conn.execute(
        sa.text(
            "UPDATE parametro_valor SET vigencia_fim = CURRENT_DATE - 1 "
            "WHERE parametro_id = :p AND escopo_ref_id IS NULL AND vigencia_fim IS NULL"
        ),
        {"p": parametro_id},
    )
    conn.execute(
        sa.text(
            "INSERT INTO parametro_valor (id, parametro_id, valor, vigencia_inicio, justificativa) "
            "VALUES (gen_random_uuid(), :p, 250, CURRENT_DATE, :just)"
        ),
        {"p": parametro_id, "just": JUSTIFICATIVA},
    )
    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )


def downgrade() -> None:
    conn = op.get_bind()
    parametro_id = conn.execute(
        sa.text("SELECT id FROM parametro WHERE chave = :chave"), {"chave": CHAVE}
    ).scalar()
    if parametro_id is None:
        return
    removida = conn.execute(
        sa.text(
            "DELETE FROM parametro_valor WHERE parametro_id = :p AND escopo_ref_id IS NULL "
            "AND justificativa = :just RETURNING vigencia_inicio"
        ),
        {"p": parametro_id, "just": JUSTIFICATIVA},
    ).scalar()
    if removida is None:
        return
    conn.execute(
        sa.text(
            "UPDATE parametro_valor SET vigencia_fim = NULL "
            "WHERE parametro_id = :p AND escopo_ref_id IS NULL AND vigencia_fim = :fim"
        ),
        {"p": parametro_id, "fim": removida - timedelta(days=1)},
    )
    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )
