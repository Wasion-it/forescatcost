"""ICMS só em Uso e Consumo: Adicionar Ativo e Industrialização ficam com alíquota 0

Revision ID: c1e4a7d9b3f5
Revises: b9d3f6a2c8e4
Create Date: 2026-10-19 16:00:00

Só dados, sem alteração de esquema. Roda apenas quando o banco já está populado (existe
componente_custo); em banco novo o seed já cria as alíquotas certas.

- ICMS de ADICIONAR_ATIVO e INDUSTRIALIZACAO passa a 0 a partir de hoje. A vigência em aberto é
  encerrada no dia anterior e uma nova é criada com alíquota 0; se a vigência começou hoje ou no
  futuro, o percentual é alterado na própria linha. Alíquotas que já são 0 não mudam;
- processos CALCULADOS desses dois tipos ficam marcados com recálculo pendente.

Downgrade: não restaura a alíquota anterior (o valor antigo está no histórico de vigências).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c1e4a7d9b3f5"
down_revision: str | Sequence[str] | None = "b9d3f6a2c8e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIPOS_SEM_ICMS = ["ADICIONAR_ATIVO", "INDUSTRIALIZACAO"]
JUSTIFICATIVA = "Sem ICMS: só Uso e Consumo recolhe ICMS (definição do PCM). Validar com o Fiscal."


def _banco_populado(conn) -> bool:
    return conn.execute(sa.text("SELECT 1 FROM componente_custo LIMIT 1")).first() is not None


def upgrade() -> None:
    conn = op.get_bind()
    if not _banco_populado(conn):
        return

    atuais = conn.execute(
        sa.text(
            "SELECT a.id, a.imposto_id, a.tipo_importacao_id, a.vigencia_inicio < CURRENT_DATE "
            "FROM aliquota a "
            "JOIN imposto i ON i.id = a.imposto_id AND i.codigo = 'ICMS' "
            "JOIN tipo_importacao t ON t.id = a.tipo_importacao_id AND t.codigo = ANY(:tipos) "
            "WHERE a.percentual <> 0 "
            "AND (a.vigencia_fim IS NULL OR a.vigencia_fim >= CURRENT_DATE)"
        ),
        {"tipos": TIPOS_SEM_ICMS},
    ).all()

    for aliquota_id, imposto_id, tipo_id, comecou_antes_de_hoje in atuais:
        if comecou_antes_de_hoje:
            conn.execute(
                sa.text("UPDATE aliquota SET vigencia_fim = CURRENT_DATE - 1 WHERE id = :id"),
                {"id": aliquota_id},
            )
            conn.execute(
                sa.text(
                    "INSERT INTO aliquota (id, imposto_id, tipo_importacao_id, percentual, "
                    "origem, vigencia_inicio, justificativa) "
                    "VALUES (gen_random_uuid(), :imposto, :tipo, 0, 'MANUAL', CURRENT_DATE, "
                    ":just)"
                ),
                {"imposto": imposto_id, "tipo": tipo_id, "just": JUSTIFICATIVA},
            )
        else:
            conn.execute(
                sa.text("UPDATE aliquota SET percentual = 0, justificativa = :just WHERE id = :id"),
                {"id": aliquota_id, "just": JUSTIFICATIVA},
            )

    conn.execute(
        sa.text(
            "UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO' "
            "AND tipo_importacao_id IN "
            "(SELECT id FROM tipo_importacao WHERE codigo = ANY(:tipos))"
        ),
        {"tipos": TIPOS_SEM_ICMS},
    )


def downgrade() -> None:
    # Dados: a alíquota anterior permanece no histórico de vigências e pode ser reativada em
    # Alíquotas. Nada a desfazer no esquema.
    pass
