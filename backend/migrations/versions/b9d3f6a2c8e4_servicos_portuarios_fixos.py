"""Armazenagem marítima: serviços portuários fixos por terminal, itemizados

Revision ID: b9d3f6a2c8e4
Revises: a8c2e5f1b7d3
Create Date: 2026-10-19 15:00:00

Só dados, sem alteração de esquema. Roda apenas quando o banco já está populado (existe
componente_custo); em banco novo o seed cria parâmetros e fórmulas.

- seis parâmetros TERMINAL do grupo "Armazenagem", com padrão 0: pesagem, infraestrutura, ISPS,
  seguro, inspeção não invasiva e serviços administrativos. São valores fixos por processo
  (não multiplicam por container);
- valores do Chibatão e da Superterminais (aba Custos Marítimos da planilha). O valor específico
  desses dois terminais em arm_mar_taxas_container é removido, para não contar em dobro; o
  parâmetro continua existindo e o valor da Santos Brasil não muda;
- nova versão da fórmula ARM_MARITIMA somando os seis fixos antes do gross-up e do mínimo;
- processos CALCULADOS ficam marcados com recálculo pendente.

Downgrade: volta a fórmula anterior (como nova versão), restaura os valores do Chibatão (1.444,76)
e da Superterminais (1.730,49) em arm_mar_taxas_container e remove os seis parâmetros.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9d3f6a2c8e4"
down_revision: str | Sequence[str] | None = "a8c2e5f1b7d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLANILHA = "Planilha Cálculo Armazenagem BR260630-C"
INICIO = "2026-01-01"

# chave, descrição
PARAMETROS = [
    ("arm_mar_pesagem", "Armazenagem marítima, pesagem de container (fixo)"),
    ("arm_mar_infra", "Armazenagem marítima, infraestrutura portuária (fixo)"),
    ("arm_mar_isps", "Armazenagem marítima, ISPS Code (fixo)"),
    ("arm_mar_seguro", "Armazenagem marítima, seguro (fixo)"),
    ("arm_mar_inspecao", "Armazenagem marítima, inspeção não invasiva (fixo)"),
    ("arm_mar_servicos_adm", "Armazenagem marítima, serviços administrativos (fixo)"),
]
CHAVES = [chave for chave, _ in PARAMETROS]

SERVICOS = {
    "Chibatão": {
        "arm_mar_pesagem": "130.02", "arm_mar_infra": "570.66", "arm_mar_isps": "99.68",
        "arm_mar_seguro": "97.65", "arm_mar_inspecao": "469.53", "arm_mar_servicos_adm": "77.22",
    },
    "Superterminais": {
        "arm_mar_pesagem": "160.28", "arm_mar_infra": "715.36", "arm_mar_isps": "122.12",
        "arm_mar_seguro": "97.65", "arm_mar_inspecao": "584.70", "arm_mar_servicos_adm": "50.38",
    },
}  # fmt: skip

# Valores de arm_mar_taxas_container que a migração a8c2e5f1b7d3 gravou e que este passo remove
TAXAS_CONTAINER_ANTERIORES = {
    "Chibatão": (
        "1444.76",
        f"{PLANILHA}: pesagem 130,02 + infraestrutura 570,66 + ISPS 99,68 + seguro 97,65 "
        "+ inspeção não invasiva 469,53 + serviços administrativos 77,22",
    ),
    "Superterminais": (
        "1730.49",
        f"{PLANILHA}: pesagem 160,28 + infraestrutura 715,36 + ISPS 122,12 + seguro 97,65 "
        "+ inspeção não invasiva 584,70 + serviços administrativos 50,38",
    ),
}

FORMULA_NOVA = (
    "se(modal == 'MARITIMO', "
    "max((cif * p.arm_mar_pct_periodo1 + qtd_containers * p.arm_mar_taxas_container "
    "+ p.arm_mar_pesagem + p.arm_mar_infra + p.arm_mar_isps + p.arm_mar_seguro "
    "+ p.arm_mar_inspecao + p.arm_mar_servicos_adm) "
    "/ (1 - p.arm_mar_pct_impostos), p.arm_mar_minimo), 0)"
)
FORMULA_ANTERIOR = (
    "se(modal == 'MARITIMO', "
    "max((cif * p.arm_mar_pct_periodo1 + qtd_containers * p.arm_mar_taxas_container) "
    "/ (1 - p.arm_mar_pct_impostos), p.arm_mar_minimo), 0)"
)


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


def _valor_terminal(conn, terminal: str, chave: str, valor: str, justificativa: str) -> None:
    conn.execute(
        sa.text(
            "INSERT INTO parametro_valor (id, parametro_id, escopo_ref_id, valor, "
            "vigencia_inicio, justificativa) "
            "SELECT gen_random_uuid(), p.id, t.id, CAST(:valor AS numeric), "
            "CAST(:inicio AS date), CAST(:just AS varchar) "
            "FROM parametro p, terminal t "
            "WHERE p.chave = CAST(:chave AS varchar) AND t.nome = CAST(:terminal AS varchar) "
            "AND NOT EXISTS (SELECT 1 FROM parametro_valor v "
            "WHERE v.parametro_id = p.id AND v.escopo_ref_id = t.id)"
        ),
        {
            "terminal": terminal,
            "chave": chave,
            "valor": valor,
            "just": justificativa,
            "inicio": INICIO,
        },
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _banco_populado(conn):
        return

    for chave, descricao in PARAMETROS:
        params = {
            "chave": chave,
            "descricao": descricao,
            "inicio": INICIO,
            "just": "Sem terminal: os serviços portuários fixos vêm do valor de cada terminal",
        }
        conn.execute(
            sa.text(
                "INSERT INTO parametro (id, chave, descricao, tipo_valor, escopo, grupo) "
                "SELECT gen_random_uuid(), CAST(:chave AS varchar), CAST(:descricao AS varchar), "
                "'MONETARIO', 'TERMINAL', 'Armazenagem' "
                "WHERE NOT EXISTS (SELECT 1 FROM parametro WHERE chave = CAST(:chave AS varchar))"
            ),
            params,
        )
        conn.execute(
            sa.text(
                "INSERT INTO parametro_valor (id, parametro_id, valor, vigencia_inicio, "
                "justificativa) "
                "SELECT gen_random_uuid(), p.id, 0, CAST(:inicio AS date), "
                "CAST(:just AS varchar) "
                "FROM parametro p WHERE p.chave = CAST(:chave AS varchar) "
                "AND NOT EXISTS (SELECT 1 FROM parametro_valor v WHERE v.parametro_id = p.id "
                "AND v.escopo_ref_id IS NULL)"
            ),
            params,
        )

    for terminal, servicos in SERVICOS.items():
        justificativa = f"{PLANILHA}, aba Custos Marítimos: serviços portuários {terminal}"
        for chave, valor in servicos.items():
            _valor_terminal(conn, terminal, chave, valor, justificativa)

    # Os serviços agora estão itemizados: remove o total por container desses dois terminais
    conn.execute(
        sa.text(
            "DELETE FROM parametro_valor WHERE parametro_id = "
            "(SELECT id FROM parametro WHERE chave = 'arm_mar_taxas_container') "
            "AND escopo_ref_id IN (SELECT id FROM terminal WHERE nome = ANY(:nomes))"
        ),
        {"nomes": list(SERVICOS)},
    )

    _publicar_formula(conn, "ARM_MARITIMA", FORMULA_NOVA)
    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )


def downgrade() -> None:
    conn = op.get_bind()
    if not _banco_populado(conn):
        return

    _publicar_formula(conn, "ARM_MARITIMA", FORMULA_ANTERIOR)

    for terminal, (valor, justificativa) in TAXAS_CONTAINER_ANTERIORES.items():
        _valor_terminal(conn, terminal, "arm_mar_taxas_container", valor, justificativa)

    conn.execute(
        sa.text(
            "DELETE FROM parametro_valor WHERE parametro_id IN "
            "(SELECT id FROM parametro WHERE chave = ANY(:chaves))"
        ),
        {"chaves": CHAVES},
    )
    conn.execute(sa.text("DELETE FROM parametro WHERE chave = ANY(:chaves)"), {"chaves": CHAVES})
    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )
