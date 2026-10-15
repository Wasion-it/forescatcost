"""IP no lugar de DI: a provisão não usa declaração real

Revision ID: 6be361b0acc2
Revises: ae5496b19e71
Create Date: 2026-10-15 08:03:39.636873

Esquema:
- importacao.numero_declaracao -> numero_ip e data_declaracao -> data_ip;
- remoção de importacao.tipo_declaracao (DI/DUIMP);
- índice único ux_importacao_declaracao (tipo + número) substituído por ux_importacao_ip
  (somente numero_ip, onde não nulo).

Dados (só quando o banco já está populado, ou seja, existe componente_custo):
- parâmetros tcif_valor_di -> tcif_valor_ip e despachante_honorario_di ->
  despachante_honorario_ip (chave e descrição);
- fórmulas TCIF e DESPACHANTE ganham nova versão com os nomes novos (a versão aberta é
  encerrada no dia anterior; versões antigas e cálculos já feitos não são alterados).

Downgrade: recria tipo_declaracao (padrão 'DI'), devolve nomes de colunas, de parâmetros e o
índice antigo, e reescreve com replace as expressões das fórmulas TCIF e DESPACHANTE. O tipo
DUIMP, que não existe mais no esquema novo, não é recuperável (todos voltam como DI).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "6be361b0acc2"
down_revision: str | Sequence[str] | None = "ae5496b19e71"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# chave antiga, chave nova, descrição antiga, descrição nova
PARAMETROS = [
    ("tcif_valor_di", "tcif_valor_ip", "TCIF por DI", "TCIF por IP"),
    (
        "despachante_honorario_di",
        "despachante_honorario_ip",
        "Honorário do despachante por DI",
        "Honorário do despachante por IP",
    ),
]

COMPONENTES_COM_FORMULA = ("TCIF", "DESPACHANTE")


def _renomear_parametros(conn, de: int, para: int) -> None:
    """Renomeia chave e descrição dos parâmetros (índices de PARAMETROS: 0/2 antigo, 1/3 novo)."""
    for item in PARAMETROS:
        conn.execute(
            sa.text(
                "UPDATE parametro SET chave = CAST(:nova AS varchar), "
                "descricao = CAST(:descricao AS varchar) WHERE chave = CAST(:antiga AS varchar)"
            ),
            {"antiga": item[de], "nova": item[para], "descricao": item[para + 2]},
        )


def _publicar_formula(conn, codigo: str, de: str, para: str) -> None:
    """Fecha a fórmula publicada em aberto (dia anterior) e publica a próxima versão,
    trocando os nomes de parâmetros na expressão."""
    atual = conn.execute(
        sa.text(
            "SELECT f.id, f.expressao, f.vigencia_inicio < CURRENT_DATE AS pode_fechar "
            "FROM formula f JOIN componente_custo c ON c.id = f.componente_id "
            "WHERE c.codigo = :codigo AND f.status = 'PUBLICADA' AND f.vigencia_fim IS NULL"
        ),
        {"codigo": codigo},
    ).first()
    if atual is None:
        return
    nova = atual.expressao.replace(de, para)
    if nova == atual.expressao:
        return
    if not atual.pode_fechar:
        # versão criada hoje: não dá para encerrá-la no dia anterior, então só reescreve
        conn.execute(
            sa.text("UPDATE formula SET expressao = :expr WHERE id = :id"),
            {"expr": nova, "id": atual.id},
        )
        return
    conn.execute(
        sa.text("UPDATE formula SET vigencia_fim = CURRENT_DATE - 1 WHERE id = :id"),
        {"id": atual.id},
    )
    conn.execute(
        sa.text(
            "INSERT INTO formula (id, componente_id, versao, expressao, status, vigencia_inicio) "
            "SELECT gen_random_uuid(), c.id, "
            "coalesce((SELECT max(f.versao) FROM formula f WHERE f.componente_id = c.id), 0) + 1, "
            ":expr, 'PUBLICADA', CURRENT_DATE "
            "FROM componente_custo c WHERE c.codigo = :codigo"
        ),
        {"codigo": codigo, "expr": nova},
    )


def _banco_populado(conn) -> bool:
    return conn.execute(sa.text("SELECT 1 FROM componente_custo LIMIT 1")).first() is not None


def upgrade() -> None:
    op.drop_index(
        "ux_importacao_declaracao",
        table_name="importacao",
        postgresql_where=sa.text("numero_declaracao IS NOT NULL"),
    )
    op.alter_column("importacao", "numero_declaracao", new_column_name="numero_ip")
    op.alter_column("importacao", "data_declaracao", new_column_name="data_ip")
    op.drop_column("importacao", "tipo_declaracao")
    op.create_index(
        "ux_importacao_ip",
        "importacao",
        ["numero_ip"],
        unique=True,
        postgresql_where=sa.text("numero_ip IS NOT NULL"),
    )

    conn = op.get_bind()
    if _banco_populado(conn):
        _renomear_parametros(conn, 0, 1)
        _publicar_formula(conn, "TCIF", "tcif_valor_di", "tcif_valor_ip")
        _publicar_formula(
            conn, "DESPACHANTE", "despachante_honorario_di", "despachante_honorario_ip"
        )


def downgrade() -> None:
    op.drop_index(
        "ux_importacao_ip",
        table_name="importacao",
        postgresql_where=sa.text("numero_ip IS NOT NULL"),
    )
    op.add_column(
        "importacao",
        sa.Column(
            "tipo_declaracao", sa.String(length=10), nullable=False, server_default="DI"
        ),
    )
    op.alter_column("importacao", "tipo_declaracao", server_default=None)
    op.alter_column("importacao", "numero_ip", new_column_name="numero_declaracao")
    op.alter_column("importacao", "data_ip", new_column_name="data_declaracao")
    op.create_index(
        "ux_importacao_declaracao",
        "importacao",
        ["tipo_declaracao", "numero_declaracao"],
        unique=True,
        postgresql_where=sa.text("numero_declaracao IS NOT NULL"),
    )

    conn = op.get_bind()
    if _banco_populado(conn):
        _renomear_parametros(conn, 1, 0)
        # reescreve as expressões no lugar (inclusive a versão aberta), sem criar versão nova
        conn.execute(
            sa.text(
                "UPDATE formula f SET expressao = "
                "replace(replace(f.expressao, 'tcif_valor_ip', 'tcif_valor_di'), "
                "'despachante_honorario_ip', 'despachante_honorario_di') "
                "FROM componente_custo c WHERE c.id = f.componente_id AND c.codigo = ANY(:codigos)"
            ),
            {"codigos": list(COMPONENTES_COM_FORMULA)},
        )
