"""auditoria por trigger e vigências sem sobreposição

Revision ID: a1b2c3d4e5f6
Revises: c87bb7f66f83
Create Date: 2026-10-13 09:00:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "c87bb7f66f83"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABELAS_AUDITADAS = [
    "usuario",
    "usuario_perfil",
    "tipo_importacao",
    "transportadora",
    "despachante",
    "terminal",
    "parametro",
    "parametro_valor",
    "imposto",
    "aliquota",
    "componente_custo",
    "formula",
    "importacao",
    "calculo",
]

FUNCAO_AUDITORIA = """
CREATE OR REPLACE FUNCTION fn_auditoria() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_antes  jsonb;
    v_depois jsonb;
    v_campos jsonb;
    v_registro text;
    v_usuario text := nullif(current_setting('app.usuario_id', true), '');
    v_correlation text := nullif(current_setting('app.correlation_id', true), '');
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        v_antes := to_jsonb(OLD) - 'senha_hash';
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        v_depois := to_jsonb(NEW) - 'senha_hash';
    END IF;

    IF TG_OP = 'UPDATE' THEN
        SELECT coalesce(jsonb_agg(d.key), '[]'::jsonb) INTO v_campos
          FROM jsonb_each(v_depois) d
         WHERE d.value IS DISTINCT FROM v_antes -> d.key
           AND d.key NOT IN ('atualizado_em', 'versao');
        IF v_campos = '[]'::jsonb THEN
            RETURN NEW;  -- nada de relevante mudou
        END IF;
    END IF;

    v_registro := coalesce(
        coalesce(v_depois, v_antes) ->> 'id',
        concat_ws(':', coalesce(v_depois, v_antes) ->> 'usuario_id',
                       coalesce(v_depois, v_antes) ->> 'perfil_id')
    );

    INSERT INTO auditoria (tabela, registro_id, acao, dados_antes, dados_depois,
                           campos_alterados, usuario_id, correlation_id)
    VALUES (TG_TABLE_NAME, v_registro, TG_OP, v_antes, v_depois,
            v_campos, v_usuario::uuid, v_correlation);

    RETURN coalesce(NEW, OLD);
END;
$$;
"""


def upgrade() -> None:
    op.execute(FUNCAO_AUDITORIA)
    for tabela in TABELAS_AUDITADAS:
        op.execute(
            f"CREATE TRIGGER trg_auditoria_{tabela} "
            f"AFTER INSERT OR UPDATE OR DELETE ON {tabela} "
            "FOR EACH ROW EXECUTE FUNCTION fn_auditoria()"
        )

    # Trilha append-only: impede alteração ou exclusão de registros de auditoria
    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_auditoria_imutavel() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'A trilha de auditoria não pode ser alterada';
        END;
        $$;
        CREATE TRIGGER trg_auditoria_imutavel BEFORE UPDATE OR DELETE ON auditoria
        FOR EACH ROW EXECUTE FUNCTION fn_auditoria_imutavel();
        """
    )

    # Vigências sem sobreposição (intervalos fechados; fim nulo = em aberto)
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        """
        ALTER TABLE parametro_valor ADD CONSTRAINT parametro_valor_sem_sobreposicao
        EXCLUDE USING gist (
            parametro_id WITH =,
            (coalesce(escopo_ref_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
            daterange(vigencia_inicio, vigencia_fim, '[]') WITH &&
        )
        """
    )
    op.execute(
        """
        ALTER TABLE aliquota ADD CONSTRAINT aliquota_sem_sobreposicao
        EXCLUDE USING gist (
            imposto_id WITH =,
            tipo_importacao_id WITH =,
            daterange(vigencia_inicio, vigencia_fim, '[]') WITH &&
        )
        """
    )
    op.execute(
        "ALTER TABLE parametro_valor ADD CONSTRAINT parametro_valor_intervalo "
        "CHECK (vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio)"
    )
    op.execute(
        "ALTER TABLE aliquota ADD CONSTRAINT aliquota_intervalo "
        "CHECK (vigencia_fim IS NULL OR vigencia_fim >= vigencia_inicio)"
    )
    op.execute(
        "ALTER TABLE aliquota ADD CONSTRAINT aliquota_percentual "
        "CHECK (percentual >= 0 AND percentual < 1)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE aliquota DROP CONSTRAINT IF EXISTS aliquota_percentual")
    op.execute("ALTER TABLE aliquota DROP CONSTRAINT IF EXISTS aliquota_intervalo")
    op.execute("ALTER TABLE parametro_valor DROP CONSTRAINT IF EXISTS parametro_valor_intervalo")
    op.execute("ALTER TABLE aliquota DROP CONSTRAINT IF EXISTS aliquota_sem_sobreposicao")
    op.execute(
        "ALTER TABLE parametro_valor DROP CONSTRAINT IF EXISTS parametro_valor_sem_sobreposicao"
    )
    op.execute("DROP TRIGGER IF EXISTS trg_auditoria_imutavel ON auditoria")
    op.execute("DROP FUNCTION IF EXISTS fn_auditoria_imutavel()")
    for tabela in TABELAS_AUDITADAS:
        op.execute(f"DROP TRIGGER IF EXISTS trg_auditoria_{tabela} ON {tabela}")
    op.execute("DROP FUNCTION IF EXISTS fn_auditoria()")
