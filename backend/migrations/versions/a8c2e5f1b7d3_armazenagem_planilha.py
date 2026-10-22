"""Armazenagem marítima e aérea calculadas como na planilha "Cálculo Armazenagem BR260630-C"

Revision ID: a8c2e5f1b7d3
Revises: f2a6c8d4e9b1
Create Date: 2026-10-19 12:00:00

Só dados, sem alteração de esquema. Roda apenas quando o banco já está populado (existe
componente_custo); em banco novo o seed cria terminais, parâmetros e fórmulas.

- terminais marítimos "Superterminais" e "Santos Brasil" (se ainda não existirem);
- cinco parâmetros do grupo "Armazenagem", escopo TERMINAL, com valor padrão:
  arm_mar_taxas_container (0), arm_mar_pct_impostos (0), arm_aer_pct (1,65%),
  arm_aer_taxa_kg (0,25) e arm_aer_minimo_peso (20,41);
- valores por terminal (Chibatão, Superterminais e Santos Brasil) para os serviços portuários,
  o gross-up de impostos e o percentual do 1º período;
- nova versão das fórmulas ARM_MARITIMA (percentual do CIF + serviços por container, com gross-up
  e mínimo) e ARM_AEREA (percentual do CIF + tarifa por kg com mínimo; o valor informado no
  processo continua prevalecendo);
- processos CALCULADOS ficam marcados com recálculo pendente.

Downgrade: volta as fórmulas anteriores (como novas versões) e remove os parâmetros novos e o
valor do 1º período do Santos Brasil. Os terminais criados são mantidos (podem estar em uso).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a8c2e5f1b7d3"
down_revision: str | Sequence[str] | None = "f2a6c8d4e9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PLANILHA = "Planilha Cálculo Armazenagem BR260630-C"
INICIO = "2026-01-01"

TERMINAIS_NOVOS = [("Superterminais", "MARITIMO"), ("Santos Brasil", "MARITIMO")]

# chave, descrição, tipo, valor padrão, justificativa do padrão
PARAMETROS = [
    ("arm_mar_taxas_container", "Armazenagem marítima, serviços portuários por container",
     "MONETARIO", "0", "Sem terminal: os serviços portuários vêm do valor de cada terminal"),
    ("arm_mar_pct_impostos",
     "Armazenagem marítima, impostos embutidos nas tarifas (PIS/COFINS + ISS)",
     "PERCENTUAL", "0", "Sem gross-up, exceto nos terminais que embutem impostos na tarifa"),
    ("arm_aer_pct", "Armazenagem aérea, percentual sobre o CIF",
     "PERCENTUAL", "0.0165", f"{PLANILHA}, aba Custos Aéreos (Manaus)"),
    ("arm_aer_taxa_kg", "Armazenagem aérea, tarifa por kg de peso bruto",
     "MONETARIO", "0.25", f"{PLANILHA}, aba Custos Aéreos (Manaus)"),
    ("arm_aer_minimo_peso", "Armazenagem aérea, mínimo da tarifa de peso",
     "MONETARIO", "20.41", f"{PLANILHA}, aba Custos Aéreos (Manaus)"),
]  # fmt: skip

# terminal, chave, valor, justificativa
VALORES_TERMINAL = [
    ("Chibatão", "arm_mar_taxas_container", "1444.76",
     f"{PLANILHA}: pesagem 130,02 + infraestrutura 570,66 + ISPS 99,68 + seguro 97,65 "
     "+ inspeção não invasiva 469,53 + serviços administrativos 77,22"),
    ("Superterminais", "arm_mar_taxas_container", "1730.49",
     f"{PLANILHA}: pesagem 160,28 + infraestrutura 715,36 + ISPS 122,12 + seguro 97,65 "
     "+ inspeção não invasiva 584,70 + serviços administrativos 50,38"),
    ("Santos Brasil", "arm_mar_pct_periodo1", "0.002",
     f"{PLANILHA}: armazenagem 1º período de 0,2% do CIF, antes do gross-up de impostos"),
    ("Santos Brasil", "arm_mar_taxas_container", "1023.02",
     f"{PLANILHA}: scanner 198 + remoção ao costado 655 + reembolso Embraport 32,72 "
     "+ processamento eletrônico 32,50 + cadastro de BL 52,40 (2 linhas), antes do gross-up"),
    ("Santos Brasil", "arm_mar_pct_impostos", "0.1425",
     f"{PLANILHA}: tarifas divididas por 0,8575 (PIS/COFINS + ISS embutidos)"),
]  # fmt: skip

FORMULAS_NOVAS = {
    "ARM_MARITIMA": (
        "se(modal == 'MARITIMO', "
        "max((cif * p.arm_mar_pct_periodo1 + qtd_containers * p.arm_mar_taxas_container) "
        "/ (1 - p.arm_mar_pct_impostos), p.arm_mar_minimo), 0)"
    ),
    "ARM_AEREA": (
        "se(modal == 'AEREO', "
        "se(arm_aerea_manual > 0, arm_aerea_manual, "
        "cif * p.arm_aer_pct + max(peso_bruto * p.arm_aer_taxa_kg, p.arm_aer_minimo_peso)), 0)"
    ),
}
FORMULAS_ANTERIORES = {
    "ARM_MARITIMA": (
        "se(modal == 'MARITIMO', max(cif * p.arm_mar_pct_periodo1, p.arm_mar_minimo), 0)"
    ),
    "ARM_AEREA": "se(modal == 'AEREO', arm_aerea_manual, 0)",
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

    for nome, modal in TERMINAIS_NOVOS:
        conn.execute(
            sa.text(
                "INSERT INTO terminal (id, nome, modal, ativo) "
                "SELECT gen_random_uuid(), CAST(:nome AS varchar), CAST(:modal AS varchar), true "
                "WHERE NOT EXISTS (SELECT 1 FROM terminal WHERE nome = CAST(:nome AS varchar))"
            ),
            {"nome": nome, "modal": modal},
        )

    for chave, descricao, tipo, valor, justificativa in PARAMETROS:
        params = {
            "chave": chave,
            "descricao": descricao,
            "tipo": tipo,
            "valor": valor,
            "just": justificativa,
            "inicio": INICIO,
        }
        conn.execute(
            sa.text(
                "INSERT INTO parametro (id, chave, descricao, tipo_valor, escopo, grupo) "
                "SELECT gen_random_uuid(), CAST(:chave AS varchar), CAST(:descricao AS varchar), "
                "CAST(:tipo AS varchar), 'TERMINAL', 'Armazenagem' "
                "WHERE NOT EXISTS (SELECT 1 FROM parametro WHERE chave = CAST(:chave AS varchar))"
            ),
            params,
        )
        conn.execute(
            sa.text(
                "INSERT INTO parametro_valor (id, parametro_id, valor, vigencia_inicio, "
                "justificativa) "
                "SELECT gen_random_uuid(), p.id, CAST(:valor AS numeric), "
                "CAST(:inicio AS date), CAST(:just AS varchar) "
                "FROM parametro p WHERE p.chave = CAST(:chave AS varchar) "
                "AND NOT EXISTS (SELECT 1 FROM parametro_valor v WHERE v.parametro_id = p.id "
                "AND v.escopo_ref_id IS NULL)"
            ),
            params,
        )

    for terminal, chave, valor, justificativa in VALORES_TERMINAL:
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

    chaves = [p[0] for p in PARAMETROS]
    conn.execute(
        sa.text(
            "DELETE FROM parametro_valor WHERE parametro_id IN "
            "(SELECT id FROM parametro WHERE chave = ANY(:chaves))"
        ),
        {"chaves": chaves},
    )
    conn.execute(sa.text("DELETE FROM parametro WHERE chave = ANY(:chaves)"), {"chaves": chaves})
    conn.execute(
        sa.text(
            "DELETE FROM parametro_valor WHERE parametro_id = "
            "(SELECT id FROM parametro WHERE chave = 'arm_mar_pct_periodo1') "
            "AND escopo_ref_id IN (SELECT id FROM terminal WHERE nome = 'Santos Brasil')"
        )
    )
    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )
