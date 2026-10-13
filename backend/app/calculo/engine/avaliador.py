"""Avaliador seguro de expressões aritméticas com Decimal.

Nunca usa eval/exec. A expressão é convertida em AST e apenas uma lista branca
de nós é aceita. Variáveis com prefixo (``p.chave``, ``aliq.ii``) são tratadas
como nomes compostos.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from decimal import ROUND_HALF_UP, Decimal, DivisionByZero, InvalidOperation, localcontext

Valor = Decimal | str

PREFIXOS_PERMITIDOS = frozenset({"p", "aliq"})
FUNCOES_PERMITIDAS = frozenset({"min", "max", "se", "arred"})
_MAX_TAMANHO_EXPRESSAO = 1000


class ErroFormula(ValueError):
    """Expressão inválida ou erro durante a avaliação."""


def _arred(valor: Decimal, casas: Decimal = Decimal(2)) -> Decimal:
    quantum = Decimal(1).scaleb(-int(casas))
    return valor.quantize(quantum, rounding=ROUND_HALF_UP)


_FUNCOES: dict[str, Callable[..., Decimal]] = {
    "min": lambda *a: min(a),
    "max": lambda *a: max(a),
    "arred": _arred,
}

_OPERADORES_BINARIOS: dict[type[ast.operator], Callable[[Decimal, Decimal], Decimal]] = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
}

_COMPARADORES: dict[type[ast.cmpop], Callable[[Valor, Valor], bool]] = {
    ast.Eq: lambda a, b: a == b,
    ast.NotEq: lambda a, b: a != b,
    ast.Lt: lambda a, b: a < b,  # type: ignore[operator]
    ast.LtE: lambda a, b: a <= b,  # type: ignore[operator]
    ast.Gt: lambda a, b: a > b,  # type: ignore[operator]
    ast.GtE: lambda a, b: a >= b,  # type: ignore[operator]
}


def _nome_variavel(no: ast.AST) -> str | None:
    """Retorna o nome da variável (simples ou ``prefixo.chave``) ou None."""
    if isinstance(no, ast.Name):
        return no.id
    if (
        isinstance(no, ast.Attribute)
        and isinstance(no.value, ast.Name)
        and no.value.id in PREFIXOS_PERMITIDOS
    ):
        return f"{no.value.id}.{no.attr}"
    return None


def compilar(expressao: str) -> ast.Expression:
    """Valida a sintaxe e a lista branca de nós. Lança ErroFormula se inválida."""
    if not expressao or not expressao.strip():
        raise ErroFormula("Expressão vazia")
    if len(expressao) > _MAX_TAMANHO_EXPRESSAO:
        raise ErroFormula("Expressão muito longa")
    try:
        arvore = ast.parse(expressao.strip(), mode="eval")
    except SyntaxError as exc:
        raise ErroFormula(f"Sintaxe inválida: {exc.msg}") from exc
    _validar(arvore.body)
    return arvore


def _validar(no: ast.AST) -> None:
    match no:
        case ast.Constant(value=valor):
            if isinstance(valor, bool) or not isinstance(valor, int | float | str):
                raise ErroFormula(f"Constante não permitida: {valor!r}")
        case ast.Name():
            if no.id in PREFIXOS_PERMITIDOS or no.id.startswith("_"):
                raise ErroFormula(f"Nome não permitido: {no.id}")
        case ast.Attribute():
            if _nome_variavel(no) is None or no.attr.startswith("_"):
                raise ErroFormula("Acesso a atributo não permitido")
        case ast.BinOp(left=esq, op=op, right=dir_):
            if type(op) not in _OPERADORES_BINARIOS:
                raise ErroFormula(f"Operador não permitido: {type(op).__name__}")
            _validar(esq)
            _validar(dir_)
        case ast.UnaryOp(op=op, operand=operando):
            if not isinstance(op, ast.USub | ast.UAdd):
                raise ErroFormula(f"Operador não permitido: {type(op).__name__}")
            _validar(operando)
        case ast.Compare(left=esq, ops=ops, comparators=comps):
            if any(type(op) not in _COMPARADORES for op in ops):
                raise ErroFormula("Comparador não permitido")
            _validar(esq)
            for c in comps:
                _validar(c)
        case ast.BoolOp(values=valores):
            for v in valores:
                _validar(v)
        case ast.Call(func=ast.Name(id=nome), args=args, keywords=kws):
            if nome not in FUNCOES_PERMITIDAS:
                raise ErroFormula(f"Função não permitida: {nome}")
            if kws:
                raise ErroFormula("Argumentos nomeados não são permitidos")
            if nome == "se" and len(args) != 3:
                raise ErroFormula("se(condição, valor_se_verdadeiro, valor_se_falso)")
            if nome in {"min", "max"} and len(args) < 2:
                raise ErroFormula(f"{nome}() exige ao menos 2 argumentos")
            if nome == "arred" and len(args) not in {1, 2}:
                raise ErroFormula("arred(valor, casas)")
            for a in args:
                _validar(a)
        case _:
            raise ErroFormula(f"Construção não permitida: {type(no).__name__}")


def variaveis_referenciadas(expressao: str) -> set[str]:
    """Conjunto de variáveis usadas na expressão (para dependências e memória)."""
    arvore = compilar(expressao)
    nomes: set[str] = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Attribute):
            nome = _nome_variavel(no)
            if nome:
                nomes.add(nome)
        elif isinstance(no, ast.Name) and no.id not in FUNCOES_PERMITIDAS:
            nomes.add(no.id)
    # Remove os prefixos isolados capturados como Name dentro de Attribute
    return {n for n in nomes if n not in PREFIXOS_PERMITIDOS}


class _Avaliador:
    def __init__(self, variaveis: Mapping[str, Valor]):
        self.variaveis = variaveis
        self.usadas: dict[str, Valor] = {}

    def avaliar(self, no: ast.AST) -> Valor | bool:
        match no:
            case ast.Expression(body=corpo):
                return self.avaliar(corpo)
            case ast.Constant(value=valor):
                return valor if isinstance(valor, str) else Decimal(str(valor))
            case ast.Name() | ast.Attribute():
                nome = _nome_variavel(no)
                assert nome is not None
                if nome not in self.variaveis:
                    if nome.startswith("p."):
                        raise ErroFormula(f"Parâmetro sem valor vigente: {nome[2:]}")
                    if nome.startswith("aliq."):
                        raise ErroFormula(f"Alíquota sem valor vigente: {nome[5:].upper()}")
                    raise ErroFormula(f"Variável não definida: {nome}")
                valor = self.variaveis[nome]
                self.usadas[nome] = valor
                return valor
            case ast.BinOp(left=esq, op=op, right=dir_):
                a, b = self._num(esq), self._num(dir_)
                return _OPERADORES_BINARIOS[type(op)](a, b)
            case ast.UnaryOp(op=op, operand=operando):
                v = self._num(operando)
                return -v if isinstance(op, ast.USub) else v
            case ast.Compare(left=esq, ops=ops, comparators=comps):
                atual = self.avaliar(esq)
                for op, comp in zip(ops, comps, strict=True):
                    prox = self.avaliar(comp)
                    if not _COMPARADORES[type(op)](atual, prox):  # type: ignore[arg-type]
                        return False
                    atual = prox
                return True
            case ast.BoolOp(op=op, values=valores):
                if isinstance(op, ast.And):
                    return all(self._bool(v) for v in valores)
                return any(self._bool(v) for v in valores)
            case ast.Call(func=ast.Name(id="se"), args=[cond, sim, nao]):
                # Avaliação preguiçosa: só o ramo escolhido é avaliado
                return self.avaliar(sim) if self._bool(cond) else self.avaliar(nao)
            case ast.Call(func=ast.Name(id=nome), args=args):
                return _FUNCOES[nome](*(self._num(a) for a in args))
        raise ErroFormula(f"Construção não suportada: {type(no).__name__}")

    def _num(self, no: ast.AST) -> Decimal:
        v = self.avaliar(no)
        if isinstance(v, bool) or not isinstance(v, Decimal):
            raise ErroFormula("Operação aritmética com valor não numérico")
        return v

    def _bool(self, no: ast.AST) -> bool:
        v = self.avaliar(no)
        if isinstance(v, bool):
            return v
        if isinstance(v, Decimal):
            return v != 0
        raise ErroFormula("Condição deve ser lógica")


def avaliar(expressao: str, variaveis: Mapping[str, Valor]) -> tuple[Decimal, dict[str, Valor]]:
    """Avalia a expressão e retorna (resultado, variáveis efetivamente usadas)."""
    arvore = compilar(expressao)
    avaliador = _Avaliador(variaveis)
    with localcontext() as ctx:
        ctx.prec = 28
        ctx.rounding = ROUND_HALF_UP
        try:
            resultado = avaliador.avaliar(arvore)
        except (DivisionByZero, InvalidOperation, ZeroDivisionError) as exc:
            raise ErroFormula("Divisão por zero ou operação inválida") from exc
    if isinstance(resultado, bool) or not isinstance(resultado, Decimal):
        raise ErroFormula("A expressão deve resultar em um número")
    return resultado, avaliador.usadas
