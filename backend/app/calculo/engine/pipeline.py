"""Pipeline de cálculo: domínio puro, sem banco e sem HTTP.

Recebe entradas do processo, componentes (com suas fórmulas), parâmetros e
alíquotas já resolvidos, e devolve um resultado por componente com memória.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from graphlib import CycleError, TopologicalSorter

from .avaliador import ErroFormula, Valor, avaliar, variaveis_referenciadas
from .competencia import RegraCompetencia, competencia

CENTAVO = Decimal("0.01")


class ErroCalculo(Exception):
    """Falha de cálculo com lista de problemas legíveis para o usuário."""

    def __init__(self, problemas: list[str]):
        super().__init__("; ".join(problemas))
        self.problemas = problemas


@dataclass(frozen=True)
class Entradas:
    data_referencia: date
    tipo_importacao: str
    modal: str
    valor_invoice: Decimal
    moeda_invoice: str
    valor_frete: Decimal
    moeda_frete: str
    qtd_itens: int
    qtd_containers: int
    taxa_usd: Decimal | None
    taxa_cny: Decimal | None
    valor_siscomex: Decimal
    peso_bruto: Decimal
    peso_liquido: Decimal
    valor_armazenagem_aerea: Decimal = Decimal(0)
    valor_taxa_liberacao: Decimal = Decimal(0)


@dataclass(frozen=True)
class Componente:
    codigo: str
    nome: str
    expressao: str
    compoe_provisao: bool
    regra_competencia: RegraCompetencia
    ordem: int = 0
    formula_id: str | None = None
    formula_versao: int | None = None

    @property
    def variavel(self) -> str:
        return self.codigo.lower()


@dataclass
class ResultadoComponente:
    codigo: str
    nome: str
    valor: Decimal
    competencia: date
    compoe_provisao: bool
    expressao: str
    variaveis: dict[str, str]
    formula_id: str | None
    formula_versao: int | None
    ordem: int


@dataclass
class ResultadoCalculo:
    itens: list[ResultadoComponente]
    variaveis_base: dict[str, str] = field(default_factory=dict)

    @property
    def total_provisionado(self) -> Decimal:
        return sum((i.valor for i in self.itens if i.compoe_provisao), Decimal(0))

    def por_codigo(self) -> dict[str, ResultadoComponente]:
        return {i.codigo: i for i in self.itens}


def _taxa(moeda: str, entradas: Entradas) -> Decimal:
    moeda = moeda.upper()
    if moeda == "BRL":
        return Decimal(1)
    taxa = {"USD": entradas.taxa_usd, "CNY": entradas.taxa_cny}.get(moeda)
    if taxa is None or taxa <= 0:
        raise ErroCalculo([f"Informe a taxa de câmbio para {moeda}"])
    return taxa


def variaveis_base(entradas: Entradas) -> dict[str, Valor]:
    """Variáveis derivadas diretamente das entradas (conversão cambial inclusa)."""
    invoice_brl = (entradas.valor_invoice * _taxa(entradas.moeda_invoice, entradas)).quantize(
        CENTAVO, rounding=ROUND_HALF_UP
    )
    frete_brl = (entradas.valor_frete * _taxa(entradas.moeda_frete, entradas)).quantize(
        CENTAVO, rounding=ROUND_HALF_UP
    )
    return {
        "valor_invoice": entradas.valor_invoice,
        "valor_frete": entradas.valor_frete,
        "invoice_brl": invoice_brl,
        "frete_brl": frete_brl,
        "siscomex": entradas.valor_siscomex,
        "valor_taxa_liberacao": entradas.valor_taxa_liberacao,
        "qtd_itens": Decimal(entradas.qtd_itens),
        "qtd_containers": Decimal(entradas.qtd_containers),
        "peso_bruto": entradas.peso_bruto,
        "peso_liquido": entradas.peso_liquido,
        "taxa_usd": entradas.taxa_usd or Decimal(0),
        "taxa_cny": entradas.taxa_cny or Decimal(0),
        "arm_aerea_manual": entradas.valor_armazenagem_aerea,
        "modal": entradas.modal.upper(),
        "tipo_importacao": entradas.tipo_importacao.upper(),
    }


# Aliases calculados a partir de componentes: nome -> expressão
ALIASES: dict[str, str] = {"valor_carga": "cif"}


def ordenar(componentes: Sequence[Componente]) -> list[Componente]:
    """Ordena por dependência (topológica). Lança ErroCalculo em ciclo."""
    por_var = {c.variavel: c for c in componentes}
    grafo: dict[str, set[str]] = {}
    for c in componentes:
        try:
            refs = variaveis_referenciadas(c.expressao)
        except ErroFormula as exc:
            raise ErroCalculo([f"{c.nome}: {exc}"]) from exc
        refs = {ALIASES.get(r, r) for r in refs}
        grafo[c.variavel] = {r for r in refs if r in por_var and r != c.variavel}
        if c.variavel in refs:
            raise ErroCalculo([f"{c.nome}: a fórmula referencia a si mesma"])
    try:
        ordem = list(TopologicalSorter(grafo).static_order())
    except CycleError as exc:
        ciclo = " → ".join(exc.args[1]) if len(exc.args) > 1 else ""
        raise ErroCalculo([f"Dependência circular entre fórmulas: {ciclo}"]) from exc
    return [por_var[v] for v in ordem]


def calcular(
    entradas: Entradas,
    componentes: Sequence[Componente],
    parametros: Mapping[str, Decimal],
    aliquotas: Mapping[str, Decimal],
    dia_corte: int = 15,
) -> ResultadoCalculo:
    """Executa o pipeline completo e retorna os resultados por componente."""
    base = variaveis_base(entradas)
    contexto: dict[str, Valor] = dict(base)
    contexto.update({f"p.{k}": v for k, v in parametros.items()})
    contexto.update({f"aliq.{k.lower()}": v for k, v in aliquotas.items()})

    resultados: list[ResultadoComponente] = []
    problemas: list[str] = []

    for comp in ordenar(componentes):
        try:
            valor_bruto, usadas = avaliar(comp.expressao, contexto)
        except ErroFormula as exc:
            problemas.append(f"{comp.nome}: {exc}")
            continue
        valor = valor_bruto.quantize(CENTAVO, rounding=ROUND_HALF_UP)
        contexto[comp.variavel] = valor
        for alias, alvo in ALIASES.items():
            if alvo == comp.variavel:
                contexto[alias] = valor
        resultados.append(
            ResultadoComponente(
                codigo=comp.codigo,
                nome=comp.nome,
                valor=valor,
                competencia=competencia(
                    entradas.data_referencia, comp.regra_competencia, dia_corte
                ),
                compoe_provisao=comp.compoe_provisao,
                expressao=comp.expressao,
                variaveis={k: str(v) for k, v in sorted(usadas.items())},
                formula_id=comp.formula_id,
                formula_versao=comp.formula_versao,
                ordem=comp.ordem,
            )
        )

    if problemas:
        raise ErroCalculo(problemas)

    resultados.sort(key=lambda r: (r.ordem, r.codigo))
    return ResultadoCalculo(
        itens=resultados,
        variaveis_base={k: str(v) for k, v in base.items()},
    )
