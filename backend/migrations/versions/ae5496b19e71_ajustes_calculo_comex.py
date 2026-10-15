"""ajustes de cálculo do comex: taxa de liberação por processo, Siscomex, II/IPI suspensos

Revision ID: ae5496b19e71
Revises: a1b2c3d4e5f6
Create Date: 2026-10-15 07:36:32.775081

Esquema:
- importacao.valor_taxa_liberacao (NOT NULL) e remoção de importacao.transportadora_secundaria_id.

Dados (só quando o banco já está populado, ou seja, existe componente_custo; em banco novo
o seed cria tudo):
- processos existentes recebem o valor global vigente de taxa_liberacao (350,00);
- transportadoras SECUNDARIO ficam inativas e SECUNDARIO/AMBOS viram LOCAL;
- parâmetros afrmm_percentual, ts_valor_container, ts_percentual e taxa_liberacao são apagados;
- componentes AFRMM e TRANSP_SEC são desativados (cálculos antigos referenciam por FK);
- parâmetros ii_suspenso e ipi_suspenso (BOOLEANO, padrão 1) e novas versões das fórmulas de
  II, IPI, ICMS e FRETE_INTL; novos componentes TAXA_SISCOMEX e TAXA_LIBERACAO;
- tipo ADICIONAR_ATIVO (alíquotas copiadas de USO_CONSUMO e honorário de R$ 900,00);
- processos CALCULADOS ficam marcados com recálculo pendente.

Downgrade: restaura o esquema, reativa AFRMM e TRANSP_SEC e recria os quatro parâmetros
removidos com os valores de exemplo do seed. Os demais dados apagados ou alterados (valores
específicos de parâmetros, vínculo de transportadora secundária, fórmulas v2) não voltam.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ae5496b19e71"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PARAMETROS_REMOVIDOS = ("afrmm_percentual", "ts_valor_container", "ts_percentual", "taxa_liberacao")

# Parâmetros recriados no downgrade: chave, descrição, tipo, escopo, grupo, valor padrão
PARAMETROS_DOWNGRADE = [
    (
        "afrmm_percentual",
        "AFRMM sobre o frete marítimo",
        "PERCENTUAL",
        "GLOBAL",
        "Impostos",
        "0.08",
    ),
    (
        "ts_valor_container",
        "Transporte secundário por container",
        "MONETARIO",
        "GLOBAL",
        "Transporte secundário",
        "1000",
    ),
    (
        "ts_percentual",
        "Transporte secundário sobre o valor da carga",
        "PERCENTUAL",
        "GLOBAL",
        "Transporte secundário",
        "0.0001",
    ),
    (
        "taxa_liberacao",
        "Taxa de liberação do frete internacional",
        "MONETARIO",
        "GLOBAL",
        "Frete internacional",
        "350",
    ),
]

FORMULAS_NOVAS = {
    "II": "se(p.ii_suspenso == 1, 0, cif * aliq.ii)",
    "IPI": "se(p.ipi_suspenso == 1, 0, (cif + ii) * aliq.ipi)",
    "ICMS": "(cif + ii + ipi + pis + cofins) / (1 - aliq.icms) * aliq.icms",
    "FRETE_INTL": "frete_brl",
}

# codigo, nome, natureza, expressão, ordem
COMPONENTES_NOVOS = [
    ("TAXA_SISCOMEX", "Taxa Siscomex", "IMPOSTO", "siscomex", 60),
    ("TAXA_LIBERACAO", "Taxa de liberação", "TAXA", "valor_taxa_liberacao", 150),
]

PARAMETROS_SUSPENSAO = [
    ("ii_suspenso", "Imposto de Importação suspenso (não paga)"),
    ("ipi_suspenso", "IPI suspenso (não paga)"),
]


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


def _migrar_dados(conn) -> None:
    # (a) taxa de liberação vigente vira o valor de cada processo existente
    conn.execute(
        sa.text(
            """
            UPDATE importacao SET valor_taxa_liberacao = coalesce((
                SELECT pv.valor FROM parametro_valor pv
                  JOIN parametro p ON p.id = pv.parametro_id
                 WHERE p.chave = 'taxa_liberacao' AND pv.escopo_ref_id IS NULL
                   AND pv.vigencia_inicio <= CURRENT_DATE
                   AND (pv.vigencia_fim IS NULL OR pv.vigencia_fim >= CURRENT_DATE)
                 ORDER BY pv.vigencia_inicio DESC LIMIT 1
            ), 0)
            """
        )
    )

    # (b) transporte secundário deixa de existir
    conn.execute(
        sa.text("UPDATE transportadora SET ativo = false WHERE tipo_servico = 'SECUNDARIO'")
    )
    conn.execute(
        sa.text(
            "UPDATE transportadora SET tipo_servico = 'LOCAL' "
            "WHERE tipo_servico IN ('SECUNDARIO', 'AMBOS')"
        )
    )

    # (c) parâmetros removidos (os snapshots dos cálculos guardam os valores usados)
    conn.execute(
        sa.text(
            "DELETE FROM parametro_valor WHERE parametro_id IN "
            "(SELECT id FROM parametro WHERE chave = ANY(:chaves))"
        ),
        {"chaves": list(PARAMETROS_REMOVIDOS)},
    )
    conn.execute(
        sa.text("DELETE FROM parametro WHERE chave = ANY(:chaves)"),
        {"chaves": list(PARAMETROS_REMOVIDOS)},
    )

    # (d) componentes removidos ficam inativos para preservar o histórico
    conn.execute(
        sa.text("UPDATE componente_custo SET ativo = false WHERE codigo IN ('AFRMM', 'TRANSP_SEC')")
    )

    # (e) II e IPI suspensos por padrão
    for chave, descricao in PARAMETROS_SUSPENSAO:
        conn.execute(
            sa.text(
                "INSERT INTO parametro (id, chave, descricao, tipo_valor, escopo, grupo) "
                "SELECT gen_random_uuid(), CAST(:chave AS varchar), CAST(:descricao AS varchar), "
                "'BOOLEANO', 'TIPO_IMPORTACAO', 'Impostos' "
                "WHERE NOT EXISTS (SELECT 1 FROM parametro WHERE chave = CAST(:chave AS varchar))"
            ),
            {"chave": chave, "descricao": descricao},
        )
        conn.execute(
            sa.text(
                "INSERT INTO parametro_valor (id, parametro_id, valor, vigencia_inicio, "
                "justificativa) "
                "SELECT gen_random_uuid(), p.id, 1, CURRENT_DATE, 'Imposto suspenso: não é pago' "
                "FROM parametro p WHERE p.chave = CAST(:chave AS varchar) "
                "AND NOT EXISTS (SELECT 1 FROM parametro_valor v WHERE v.parametro_id = p.id)"
            ),
            {"chave": chave},
        )

    # (f) novas versões das fórmulas existentes
    for codigo, expressao in FORMULAS_NOVAS.items():
        _publicar_formula(conn, codigo, expressao)
    conn.execute(
        sa.text(
            "UPDATE componente_custo SET nome = 'Frete internacional' WHERE codigo = 'FRETE_INTL'"
        )
    )

    # (g) novos componentes
    for codigo, nome, natureza, expressao, ordem in COMPONENTES_NOVOS:
        conn.execute(
            sa.text(
                "INSERT INTO componente_custo (id, codigo, nome, natureza, compoe_provisao, "
                "regra_competencia, ordem, ativo) "
                "SELECT gen_random_uuid(), CAST(:codigo AS varchar), CAST(:nome AS varchar), "
                "CAST(:natureza AS varchar), true, 'MES_REFERENCIA', CAST(:ordem AS integer), true "
                "WHERE NOT EXISTS "
                "(SELECT 1 FROM componente_custo WHERE codigo = CAST(:codigo AS varchar))"
            ),
            {"codigo": codigo, "nome": nome, "natureza": natureza, "ordem": ordem},
        )
        _publicar_formula(conn, codigo, expressao)

    # (h) tipo Adicionar Ativo: alíquotas de Uso e Consumo (exemplo) e honorário de R$ 900,00
    conn.execute(
        sa.text(
            "INSERT INTO tipo_importacao (id, codigo, nome, ativo) "
            "SELECT gen_random_uuid(), 'ADICIONAR_ATIVO', 'Adicionar Ativo', true "
            "WHERE NOT EXISTS (SELECT 1 FROM tipo_importacao WHERE codigo = 'ADICIONAR_ATIVO')"
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO aliquota (id, imposto_id, tipo_importacao_id, percentual, origem,
                                  vigencia_inicio, vigencia_fim, justificativa)
            SELECT gen_random_uuid(), a.imposto_id, novo.id, a.percentual, 'MANUAL',
                   a.vigencia_inicio, a.vigencia_fim,
                   'Copiado de Uso e Consumo (exemplo). Validar com o Fiscal.'
              FROM aliquota a
              JOIN tipo_importacao uc ON uc.id = a.tipo_importacao_id AND uc.codigo = 'USO_CONSUMO'
              JOIN tipo_importacao novo ON novo.codigo = 'ADICIONAR_ATIVO'
             WHERE a.vigencia_inicio <= CURRENT_DATE
               AND (a.vigencia_fim IS NULL OR a.vigencia_fim >= CURRENT_DATE)
               AND NOT EXISTS (SELECT 1 FROM aliquota x WHERE x.tipo_importacao_id = novo.id)
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO parametro_valor (id, parametro_id, escopo_ref_id, valor, vigencia_inicio,
                                         justificativa)
            SELECT gen_random_uuid(), p.id, novo.id, 900, CURRENT_DATE,
                   'Valor informado pelo PCM (Adicionar Ativo)'
              FROM parametro p
              JOIN tipo_importacao novo ON novo.codigo = 'ADICIONAR_ATIVO'
             WHERE p.chave = 'despachante_honorario_di'
               AND NOT EXISTS (
                   SELECT 1 FROM parametro_valor v
                    WHERE v.parametro_id = p.id AND v.escopo_ref_id = novo.id)
            """
        )
    )

    # (i) as regras mudaram: todo processo calculado precisa ser recalculado
    conn.execute(
        sa.text("UPDATE importacao SET calculo_desatualizado = true WHERE status = 'CALCULADO'")
    )


def upgrade() -> None:
    op.add_column(
        "importacao",
        sa.Column(
            "valor_taxa_liberacao",
            sa.Numeric(precision=18, scale=2),
            nullable=False,
            server_default="0",
        ),
    )
    op.alter_column("importacao", "valor_taxa_liberacao", server_default=None)

    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM componente_custo LIMIT 1")).first():
        _migrar_dados(conn)

    op.drop_column("importacao", "transportadora_secundaria_id")


def downgrade() -> None:
    op.add_column(
        "importacao",
        sa.Column(
            "transportadora_secundaria_id",
            sa.Uuid(),
            sa.ForeignKey("transportadora.id"),
            nullable=True,
        ),
    )
    op.drop_column("importacao", "valor_taxa_liberacao")

    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM componente_custo LIMIT 1")).first():
        conn.execute(
            sa.text(
                "UPDATE componente_custo SET ativo = true WHERE codigo IN ('AFRMM', 'TRANSP_SEC')"
            )
        )
        for chave, descricao, tipo, escopo, grupo, valor in PARAMETROS_DOWNGRADE:
            params = {
                "chave": chave,
                "descricao": descricao,
                "tipo": tipo,
                "escopo": escopo,
                "grupo": grupo,
                "valor": valor,
            }
            conn.execute(
                sa.text(
                    "INSERT INTO parametro (id, chave, descricao, tipo_valor, escopo, grupo) "
                    "SELECT gen_random_uuid(), CAST(:chave AS varchar), "
                    "CAST(:descricao AS varchar), CAST(:tipo AS varchar), "
                    "CAST(:escopo AS varchar), CAST(:grupo AS varchar) "
                    "WHERE NOT EXISTS "
                    "(SELECT 1 FROM parametro WHERE chave = CAST(:chave AS varchar))"
                ),
                params,
            )
            conn.execute(
                sa.text(
                    "INSERT INTO parametro_valor (id, parametro_id, valor, vigencia_inicio, "
                    "justificativa) "
                    "SELECT gen_random_uuid(), p.id, CAST(:valor AS numeric), CURRENT_DATE, "
                    "'Restaurado no downgrade (valor de exemplo)' "
                    "FROM parametro p WHERE p.chave = CAST(:chave AS varchar) "
                    "AND NOT EXISTS (SELECT 1 FROM parametro_valor v WHERE v.parametro_id = p.id)"
                ),
                params,
            )
