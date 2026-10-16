"""Orquestração do cálculo: carrega insumos vigentes, executa o motor e versiona."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.calculo.engine import Entradas, ResultadoCalculo, calcular
from app.core.erros import ErroNegocio
from app.models import Calculo, CalculoItem, ComponenteCusto, Importacao, Usuario
from app.modules.parametros.service import (
    ParametroResolvido,
    carregar_componentes,
    resolver_aliquotas,
    resolver_parametros,
)


@dataclass
class Execucao:
    resultado: ResultadoCalculo
    componentes: dict[str, ComponenteCusto]
    parametros: dict[str, ParametroResolvido]
    aliquotas: dict[str, Decimal]
    data_parametros: date
    data_referencia: date
    dia_corte: int


def entradas_de(imp: Importacao) -> Entradas:
    if imp.data_referencia is None:
        raise ErroNegocio("Informe a data da IP ou a data prevista antes de calcular")
    return Entradas(
        data_referencia=imp.data_referencia,
        tipo_importacao=imp.tipo_importacao.codigo,
        modal=imp.modal,
        valor_invoice=imp.valor_invoice,
        moeda_invoice=imp.moeda_invoice,
        valor_frete=imp.valor_frete,
        moeda_frete=imp.moeda_frete,
        qtd_itens=imp.qtd_itens,
        qtd_containers=imp.qtd_containers,
        taxa_usd=imp.taxa_usd,
        taxa_cny=imp.taxa_cny,
        valor_siscomex=imp.valor_siscomex,
        peso_bruto=imp.peso_bruto_kg,
        peso_liquido=imp.peso_liquido_kg,
        valor_armazenagem_aerea=imp.valor_armazenagem_aerea,
        valor_taxa_liberacao=imp.valor_taxa_liberacao,
    )


def executar(db: Session, imp: Importacao, data_parametros: date | None = None) -> Execucao:
    if imp.status == "CANCELADO":
        raise ErroNegocio("Processo cancelado não pode ser calculado")
    if imp.status == "FECHADO":
        raise ErroNegocio("Processo fechado não pode ser calculado")
    data_parametros = data_parametros or date.today()
    entradas = entradas_de(imp)
    pares = carregar_componentes(db, data_parametros)
    parametros = resolver_parametros(db, imp, data_parametros)
    aliquotas = resolver_aliquotas(db, imp.tipo_importacao_id, data_parametros)
    corte = parametros.get("competencia_dia_corte")
    dia_corte = int(corte.valor) if corte else 15
    resultado = calcular(
        entradas,
        [c for c, _ in pares],
        {k: v.valor for k, v in parametros.items()},
        aliquotas,
        dia_corte=dia_corte,
    )
    return Execucao(
        resultado=resultado,
        componentes={orm.codigo: orm for _, orm in pares},
        parametros=parametros,
        aliquotas=aliquotas,
        data_parametros=data_parametros,
        data_referencia=entradas.data_referencia,
        dia_corte=dia_corte,
    )


def _memoria(item, execucao: Execucao) -> dict:
    origens = {}
    for var in item.variaveis:
        if var.startswith("p.") and (p := execucao.parametros.get(var[2:])):
            rotulo = "valor específico" if p.origem == "ESPECIFICO" else "valor padrão"
            origens[var] = f"{rotulo}, vigente desde {p.vigencia_inicio.isoformat()}"
        elif var.startswith("aliq."):
            origens[var] = "tabela de alíquotas"
    memoria = {
        "expressao": item.expressao,
        "formula_versao": item.formula_versao,
        "variaveis": item.variaveis,
        "origens": origens,
    }
    if any(
        var.startswith("p.") and var.endswith("_suspenso") and Decimal(valor) != 0
        for var, valor in item.variaveis.items()
    ):
        memoria["suspenso"] = True
    return memoria


def itens_saida(execucao: Execucao) -> list[dict]:
    saida = []
    for item in execucao.resultado.itens:
        comp = execucao.componentes[item.codigo]
        saida.append(
            {
                "componente_codigo": item.codigo,
                "componente_nome": item.nome,
                "natureza": comp.natureza,
                "expressao": item.expressao,
                "formula_versao": item.formula_versao,
                "valor": item.valor,
                "competencia": item.competencia,
                "compoe_provisao": item.compoe_provisao,
                "ordem": item.ordem,
                "memoria": _memoria(item, execucao),
            }
        )
    return saida


def calculo_vigente(db: Session, importacao_id) -> Calculo | None:
    return db.scalar(
        select(Calculo).where(Calculo.importacao_id == importacao_id, Calculo.vigente.is_(True))
    )


def previa(db: Session, imp: Importacao) -> dict:
    execucao = executar(db, imp)
    vigente = calculo_vigente(db, imp.id)
    anteriores = {i.componente_codigo: i.valor for i in vigente.itens} if vigente else {}
    diferencas = {}
    for item in execucao.resultado.itens:
        anterior = anteriores.get(item.codigo)
        diferencas[item.codigo] = {
            "anterior": anterior,
            "novo": item.valor,
            "diferenca": item.valor - (anterior or Decimal(0)),
        }
    return {
        "itens": itens_saida(execucao),
        "total_provisionado": execucao.resultado.total_provisionado,
        "total_anterior": vigente.total_provisionado if vigente else None,
        "diferencas": diferencas,
        "variaveis_base": execucao.resultado.variaveis_base,
        "exige_motivo": vigente is not None,
    }


def _snapshot_entradas(imp: Importacao, execucao: Execucao) -> dict:
    campos = [
        "numero_ip", "data_ip", "data_prevista", "modal",
        "valor_invoice", "moeda_invoice", "valor_frete", "moeda_frete", "qtd_itens",
        "qtd_containers", "taxa_usd", "taxa_cny", "valor_siscomex", "peso_bruto_kg",
        "peso_liquido_kg", "valor_armazenagem_aerea", "valor_taxa_liberacao",
    ]  # fmt: skip
    dados = {c: getattr(imp, c) for c in campos}
    dados["tipo_importacao"] = imp.tipo_importacao.codigo
    dados["variaveis_base"] = execucao.resultado.variaveis_base
    return json.loads(json.dumps(dados, default=str))


def _snapshot_parametros(execucao: Execucao) -> dict:
    return {
        "data_parametros": execucao.data_parametros.isoformat(),
        "dia_corte": execucao.dia_corte,
        "parametros": {
            k: {
                "valor": str(v.valor),
                "origem": v.origem,
                "vigencia_inicio": v.vigencia_inicio.isoformat(),
            }
            for k, v in sorted(execucao.parametros.items())
        },
        "aliquotas": {k: str(v) for k, v in sorted(execucao.aliquotas.items())},
    }


def registrar(db: Session, imp: Importacao, motivo: str | None, usuario: Usuario) -> Calculo:
    execucao = executar(db, imp)
    vigente = calculo_vigente(db, imp.id)
    motivo = (motivo or "").strip()
    if vigente is not None and len(motivo) < 5:
        raise ErroNegocio("Informe o motivo do recálculo (mínimo de 5 caracteres)")

    proxima = (
        db.scalar(select(func.max(Calculo.numero_versao)).where(Calculo.importacao_id == imp.id))
        or 0
    ) + 1
    entradas = _snapshot_entradas(imp, execucao)
    parametros = _snapshot_parametros(execucao)
    itens = itens_saida(execucao)
    conteudo = json.dumps(
        {"entradas": entradas, "parametros": parametros, "itens": itens},
        default=str,
        sort_keys=True,
    )

    if vigente is not None:
        db.execute(update(Calculo).where(Calculo.id == vigente.id).values(vigente=False))
        db.flush()

    calculo = Calculo(
        importacao_id=imp.id,
        numero_versao=proxima,
        vigente=True,
        data_parametros=execucao.data_parametros,
        data_referencia=execucao.data_referencia,
        motivo=motivo or "Cálculo inicial",
        entradas_snapshot=entradas,
        parametros_snapshot=parametros,
        total_provisionado=execucao.resultado.total_provisionado,
        hash_integridade=hashlib.sha256(conteudo.encode("utf-8")).hexdigest(),
        calculado_por=usuario.id,
    )
    for item in itens:
        comp = execucao.componentes[item["componente_codigo"]]
        calculo.itens.append(
            CalculoItem(
                componente_id=comp.id,
                formula_id=next(
                    (f.id for f in comp.formulas if f.versao == item["formula_versao"]), None
                ),
                **{k: v for k, v in item.items()},
            )
        )
    db.add(calculo)
    imp.status = "CALCULADO"
    imp.calculo_desatualizado = False
    db.flush()
    return calculo


def para_saida(calculo: Calculo) -> dict:
    return {
        "id": calculo.id,
        "numero_versao": calculo.numero_versao,
        "vigente": calculo.vigente,
        "data_parametros": calculo.data_parametros,
        "data_referencia": calculo.data_referencia,
        "motivo": calculo.motivo,
        "total_provisionado": calculo.total_provisionado,
        "hash_integridade": calculo.hash_integridade,
        "calculado_em": calculo.calculado_em,
        "calculado_por_nome": calculo.usuario.nome if calculo.usuario else None,
        "itens": calculo.itens,
    }
