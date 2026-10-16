"""Taxa Siscomex calculada pelo motor (valor por DI + faixas por adição)

Revision ID: b7c3a91d5e20
Revises: de8694379202
Create Date: 2026-10-15 10:30:00

Só dados, sem alteração de esquema. Roda apenas quando o banco já está populado (existe
componente_custo); em banco novo o seed cria parâmetros e fórmulas.

- sete parâmetros GLOBAIS do grupo "Siscomex" (Portaria ME 4.131/2021): R$ 115,67 por DI/Duimp
  e o valor por adição em seis faixas (38,56 / 30,85 / 23,14 / 15,42 / 7,71 / 3,86);
- nova versão da fórmula de TAXA_SISCOMEX: usa o valor informado no processo quando maior que
  zero; caso contrário calcula pelas faixas, estimando as adições por qtd_itens;
- nova versão da fórmula de CIF: passa a somar o componente taxa_siscomex (e não mais a variável
  de entrada siscomex), para que o valor calculado também entre na base dos impostos;
- processos CALCULADOS ficam marcados com recálculo pendente.

Downgrade: volta as fórmulas anteriores (como novas versões) e remove os parâmetros.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7c3a91d5e20"
down_revision: str | Sequence[str] | None = "de8694379202"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# chave, descrição, valor
PARAMETROS = [
    ("siscomex_registro", "Siscomex, valor por DI/Duimp", "115.67"),
    ("siscomex_adicao_faixa1", "Siscomex por adição, da 1ª à 2ª", "38.56"),
    ("siscomex_adicao_faixa2", "Siscomex por adição, da 3ª à 5ª", "30.85"),
    ("siscomex_adicao_faixa3", "Siscomex por adição, da 6ª à 10ª", "23.14"),
    ("siscomex_adicao_faixa4", "Siscomex por adição, da 11ª à 20ª", "15.42"),
    ("siscomex_adicao_faixa5", "Siscomex por adição, da 21ª à 50ª", "7.71"),
    ("siscomex_adicao_faixa6", "Siscomex por adição, da 51ª em diante", "3.86"),
]

FORMULA_TAXA_SISCOMEX = (
    "se(siscomex > 0, siscomex, "
    "p.siscomex_registro "
    "+ min(qtd_itens, 2) * p.siscomex_adicao_faixa1 "
    "+ max(min(qtd_itens, 5) - 2, 0) * p.siscomex_adicao_faixa2 "
    "+ max(min(qtd_itens, 10) - 5, 0) * p.siscomex_adicao_faixa3 "
    "+ max(min(qtd_itens, 20) - 10, 0) * p.siscomex_adicao_faixa4 "
    "+ max(min(qtd_itens, 50) - 20, 0) * p.siscomex_adicao_faixa5 "
    "+ max(qtd_itens - 50, 0) * p.siscomex_adicao_faixa6)"
)
FORMULAS_NOVAS = {
    "CIF": "invoice_brl + frete_brl + taxa_siscomex",
    "TAXA_SISCOMEX": FORMULA_TAXA_SISCOMEX,
}
FORMULAS_ANTERIORES = {
    "CIF": "invoice_brl + frete_brl + siscomex",
    "TAXA_SISCOMEX": "siscomex",
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


def upgrade() -> None:
    conn = op.get_bind()
    if not _banco_populado(conn):
        return

    for chave, descricao, valor in PARAMETROS:
        params = {"chave": chave, "descricao": descricao, "valor": valor}
        conn.execute(
            sa.text(
                "INSERT INTO parametro (id, chave, descricao, tipo_valor, escopo, grupo) "
                "SELECT gen_random_uuid(), CAST(:chave AS varchar), CAST(:descricao AS varchar), "
                "'MONETARIO', 'GLOBAL', 'Siscomex' "
                "WHERE NOT EXISTS (SELECT 1 FROM parametro WHERE chave = CAST(:chave AS varchar))"
            ),
            params,
        )
        conn.execute(
            sa.text(
                "INSERT INTO parametro_valor (id, parametro_id, valor, vigencia_inicio, "
                "justificativa) "
                "SELECT gen_random_uuid(), p.id, CAST(:valor AS numeric), DATE '2021-06-01', "
                "'Portaria ME 4.131/2021 (vigente desde jun/2021)' "
                "FROM parametro p WHERE p.chave = CAST(:chave AS varchar) "
                "AND NOT EXISTS (SELECT 1 FROM parametro_valor v WHERE v.parametro_id = p.id)"
            ),
            params,
        )

    for codigo, expressao in FORMULAS_NOVAS.items():
        _publicar_formula(conn, codigo, expressao)

    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not _banco_populado(conn):
        return

    for codigo, expressao in FORMULAS_ANTERIORES.items():
        _publicar_formula(conn, codigo, expressao)

    chaves = [chave for chave, _, _ in PARAMETROS]
    conn.execute(
        sa.text(
            "DELETE FROM parametro_valor WHERE parametro_id IN "
            "(SELECT id FROM parametro WHERE chave = ANY(:chaves))"
        ),
        {"chaves": chaves},
    )
    conn.execute(sa.text("DELETE FROM parametro WHERE chave = ANY(:chaves)"), {"chaves": chaves})
    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )
