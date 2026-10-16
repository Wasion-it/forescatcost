"""Resolução e manutenção de parâmetros, alíquotas e fórmulas com vigência."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.calculo.engine import Componente, ErroFormula, RegraCompetencia, compilar
from app.core.erros import ErroNegocio
from app.models import (
    Aliquota,
    ComponenteCusto,
    Formula,
    Importacao,
    Imposto,
    Parametro,
    ParametroValor,
)

ESCOPOS = {
    "GLOBAL",
    "TIPO_IMPORTACAO",
    "TRANSP_LOCAL",
    "DESPACHANTE",
    "TERMINAL",
}


def _vigente_em(coluna_inicio, coluna_fim, data: date):
    return and_(coluna_inicio <= data, or_(coluna_fim.is_(None), coluna_fim >= data))


def ref_do_escopo(imp: Importacao, escopo: str) -> uuid.UUID | None:
    return {
        "GLOBAL": None,
        "TIPO_IMPORTACAO": imp.tipo_importacao_id,
        "TRANSP_LOCAL": imp.transportadora_local_id,
        "DESPACHANTE": imp.despachante_id,
        "TERMINAL": imp.terminal_id,
    }[escopo]


@dataclass
class ParametroResolvido:
    chave: str
    valor: Decimal
    origem: str  # ESPECIFICO | PADRAO
    vigencia_inicio: date
    parametro_valor_id: uuid.UUID


def resolver_parametros(db: Session, imp: Importacao, data: date) -> dict[str, ParametroResolvido]:
    """Para cada parâmetro, usa o valor do escopo do processo; senão, o valor padrão (sem ref)."""
    linhas = db.execute(
        select(Parametro, ParametroValor)
        .join(ParametroValor, ParametroValor.parametro_id == Parametro.id)
        .where(_vigente_em(ParametroValor.vigencia_inicio, ParametroValor.vigencia_fim, data))
    ).all()
    resolvidos: dict[str, ParametroResolvido] = {}
    for parametro, pv in linhas:
        ref = ref_do_escopo(imp, parametro.escopo)
        if pv.escopo_ref_id is not None and pv.escopo_ref_id != ref:
            continue
        especifico = pv.escopo_ref_id is not None
        atual = resolvidos.get(parametro.chave)
        if atual is None or (especifico and atual.origem == "PADRAO"):
            resolvidos[parametro.chave] = ParametroResolvido(
                parametro.chave,
                pv.valor,
                "ESPECIFICO" if especifico else "PADRAO",
                pv.vigencia_inicio,
                pv.id,
            )
    return resolvidos


def resolver_aliquotas(
    db: Session, tipo_importacao_id: uuid.UUID, data: date
) -> dict[str, Decimal]:
    linhas = db.execute(
        select(Imposto.codigo, Aliquota.percentual)
        .join(Aliquota, Aliquota.imposto_id == Imposto.id)
        .where(
            Imposto.ativo.is_(True),
            Aliquota.tipo_importacao_id == tipo_importacao_id,
            _vigente_em(Aliquota.vigencia_inicio, Aliquota.vigencia_fim, data),
        )
    ).all()
    return {codigo: percentual for codigo, percentual in linhas}


def carregar_componentes(db: Session, data: date) -> list[tuple[Componente, ComponenteCusto]]:
    componentes = db.scalars(
        select(ComponenteCusto)
        .where(ComponenteCusto.ativo.is_(True))
        .order_by(ComponenteCusto.ordem)
    ).all()
    resultado: list[tuple[Componente, ComponenteCusto]] = []
    faltando: list[str] = []
    for c in componentes:
        formula = formula_vigente(c, data)
        if formula is None:
            faltando.append(f"{c.nome}: sem fórmula publicada vigente")
            continue
        resultado.append(
            (
                Componente(
                    codigo=c.codigo,
                    nome=c.nome,
                    expressao=formula.expressao,
                    compoe_provisao=c.compoe_provisao,
                    regra_competencia=RegraCompetencia(c.regra_competencia),
                    ordem=c.ordem,
                    formula_id=str(formula.id),
                    formula_versao=formula.versao,
                ),
                c,
            )
        )
    if faltando:
        raise ErroNegocio("Há componentes sem fórmula vigente", problemas=faltando)
    return resultado


def nova_vigencia_parametro(
    db: Session,
    parametro: Parametro,
    escopo_ref_id: uuid.UUID | None,
    valor: Decimal,
    inicio: date,
    justificativa: str,
    usuario_id: uuid.UUID,
) -> ParametroValor:
    """Encerra a vigência em aberto (no dia anterior) e cria a nova."""
    if escopo_ref_id is not None and parametro.escopo == "GLOBAL":
        raise ErroNegocio("Parâmetro global não aceita valor por escopo")
    if parametro.tipo_valor == "PERCENTUAL" and not (0 <= valor < 1):
        raise ErroNegocio("Percentual deve estar entre 0 e 1 (ex.: 0,0092 para 0,92%)")
    if parametro.tipo_valor == "BOOLEANO" and valor not in (Decimal(0), Decimal(1)):
        raise ErroNegocio("Informe 1 (sim) ou 0 (não)")
    if valor < 0:
        raise ErroNegocio("O valor não pode ser negativo")

    filtro_ref = (
        ParametroValor.escopo_ref_id.is_(None)
        if escopo_ref_id is None
        else ParametroValor.escopo_ref_id == escopo_ref_id
    )
    posteriores = db.scalar(
        select(ParametroValor.id).where(
            ParametroValor.parametro_id == parametro.id,
            filtro_ref,
            ParametroValor.vigencia_inicio >= inicio,
        )
    )
    if posteriores:
        raise ErroNegocio(
            "Já existe vigência iniciando nesta data ou depois. "
            "Escolha uma data de início posterior à vigência atual."
        )
    aberta = db.scalar(
        select(ParametroValor).where(
            ParametroValor.parametro_id == parametro.id,
            filtro_ref,
            ParametroValor.vigencia_fim.is_(None),
        )
    )
    if aberta is not None:
        aberta.vigencia_fim = inicio - timedelta(days=1)
        db.flush()
    novo = ParametroValor(
        parametro_id=parametro.id,
        escopo_ref_id=escopo_ref_id,
        valor=valor,
        vigencia_inicio=inicio,
        justificativa=justificativa,
        criado_por=usuario_id,
    )
    db.add(novo)
    db.flush()
    return novo


def nova_vigencia_aliquota(
    db: Session,
    imposto_id: uuid.UUID,
    tipo_importacao_id: uuid.UUID,
    percentual: Decimal,
    inicio: date,
    justificativa: str,
    origem: str,
    usuario_id: uuid.UUID,
) -> Aliquota:
    if not (0 <= percentual < 1):
        raise ErroNegocio("Alíquota deve estar entre 0 e 1 (ex.: 0,18 para 18%)")
    base = (Aliquota.imposto_id == imposto_id, Aliquota.tipo_importacao_id == tipo_importacao_id)
    if db.scalar(select(Aliquota.id).where(*base, Aliquota.vigencia_inicio >= inicio)):
        raise ErroNegocio(
            "Já existe vigência iniciando nesta data ou depois. "
            "Escolha uma data de início posterior à vigência atual."
        )
    aberta = db.scalar(select(Aliquota).where(*base, Aliquota.vigencia_fim.is_(None)))
    if aberta is not None:
        aberta.vigencia_fim = inicio - timedelta(days=1)
        db.flush()
    nova = Aliquota(
        imposto_id=imposto_id,
        tipo_importacao_id=tipo_importacao_id,
        percentual=percentual,
        origem=origem,
        vigencia_inicio=inicio,
        justificativa=justificativa,
        criado_por=usuario_id,
    )
    db.add(nova)
    db.flush()
    return nova


def validar_expressao(expressao: str) -> None:
    try:
        compilar(expressao)
    except ErroFormula as exc:
        raise ErroNegocio(f"Fórmula inválida: {exc}") from exc


def formula_vigente(componente: ComponenteCusto, data: date) -> Formula | None:
    return next(
        (
            f
            for f in componente.formulas
            if f.status == "PUBLICADA"
            and f.vigencia_inicio <= data
            and (f.vigencia_fim is None or f.vigencia_fim >= data)
        ),
        None,
    )
