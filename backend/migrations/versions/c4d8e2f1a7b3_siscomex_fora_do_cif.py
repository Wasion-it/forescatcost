"""Taxa Siscomex fora do CIF (valor aduaneiro) e somada só na base do ICMS

Revision ID: c4d8e2f1a7b3
Revises: b7c3a91d5e20
Create Date: 2026-10-15 16:00:00

Só dados, sem alteração de esquema. Roda apenas quando o banco já está populado; em banco
novo o seed cria as fórmulas a partir de app/calculo/formulas_padrao.py.

Motivo: na DI o CIF é o valor aduaneiro (FOB + frete), sem a Taxa Siscomex. A taxa não entra
na base de II, IPI, PIS e COFINS, mas entra na base do ICMS. Comparação feita com a DI do
processo IMP-00010.

- nova versão da fórmula de CIF: invoice_brl + frete_brl;
- nova versão da fórmula de ICMS: soma taxa_siscomex na base (para o ICMS não perder o valor);
- processos CALCULADOS ficam marcados com recálculo pendente. Versões de cálculo já
  registradas não mudam.

Downgrade: volta as fórmulas anteriores (como novas versões).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4d8e2f1a7b3"
down_revision: str | Sequence[str] | None = "b7c3a91d5e20"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORMULAS_NOVAS = {
    "CIF": "invoice_brl + frete_brl",
    "ICMS": "(cif + taxa_siscomex + ii + ipi + pis + cofins) / (1 - aliq.icms) * aliq.icms",
}
FORMULAS_ANTERIORES = {
    "CIF": "invoice_brl + frete_brl + taxa_siscomex",
    "ICMS": "(cif + ii + ipi + pis + cofins) / (1 - aliq.icms) * aliq.icms",
}


def _publicar_formula(conn, codigo: str, expressao: str) -> None:
    """Fecha a fórmula publicada em aberto (dia anterior) e publica a próxima versão."""
    ja_vigente = conn.execute(
        sa.text(
            "SELECT 1 FROM formula f JOIN componente_custo c ON c.id = f.componente_id "
            "WHERE c.codigo = :codigo AND f.status = 'PUBLICADA' "
            "AND f.vigencia_fim IS NULL AND f.expressao = :expr"
        ),
        {"codigo": codigo, "expr": expressao},
    ).first()
    if ja_vigente:
        return
    conn.execute(
        sa.text(
            "UPDATE formula f SET vigencia_fim = CURRENT_DATE - 1 "
            "FROM componente_custo c "
            "WHERE c.id = f.componente_id AND c.codigo = :codigo "
            "AND f.status = 'PUBLICADA' AND f.vigencia_fim IS NULL"
        ),
        {"codigo": codigo},
    )
    conn.execute(
        sa.text(
            "INSERT INTO formula (id, componente_id, versao, expressao, status, vigencia_inicio) "
            "SELECT gen_random_uuid(), c.id, "
            "coalesce((SELECT max(f.versao) FROM formula f WHERE f.componente_id = c.id), 0) + 1, "
            ":expr, 'PUBLICADA', CURRENT_DATE "
            "FROM componente_custo c WHERE c.codigo = :codigo"
        ),
        {"codigo": codigo, "expr": expressao},
    )


def _banco_populado(conn) -> bool:
    return conn.execute(sa.text("SELECT 1 FROM componente_custo LIMIT 1")).first() is not None


def _aplicar(formulas: dict[str, str]) -> None:
    conn = op.get_bind()
    if not _banco_populado(conn):
        return
    for codigo, expressao in formulas.items():
        _publicar_formula(conn, codigo, expressao)
    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )


def upgrade() -> None:
    _aplicar(FORMULAS_NOVAS)


def downgrade() -> None:
    _aplicar(FORMULAS_ANTERIORES)
