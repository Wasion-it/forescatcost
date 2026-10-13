from decimal import Decimal

import pytest

from app.calculo.engine import ErroFormula, avaliar, compilar, variaveis_referenciadas

D = Decimal


def test_aritmetica_decimal_exata():
    valor, _ = avaliar("0.1 + 0.2", {})
    assert valor == D("0.3")


def test_variaveis_com_prefixo_e_registro_de_uso():
    valor, usadas = avaliar(
        "cif * aliq.ii + p.taxa", {"cif": D("100"), "aliq.ii": D("0.14"), "p.taxa": D("5")}
    )
    assert valor == D("19.00")
    assert set(usadas) == {"cif", "aliq.ii", "p.taxa"}


def test_se_e_preguicoso_nao_avalia_ramo_falso():
    # p.inexistente não está no contexto, mas o ramo não é avaliado
    valor, usadas = avaliar("se(modal == 'AEREO', p.inexistente, 0)", {"modal": "MARITIMO"})
    assert valor == 0
    assert "p.inexistente" not in usadas


def test_min_max_arred():
    assert avaliar("max(1, 2.5, 2)", {})[0] == D("2.5")
    assert avaliar("min(3, 2)", {})[0] == D("2")
    assert avaliar("arred(2.345, 2)", {})[0] == D("2.35")


def test_variaveis_referenciadas():
    refs = variaveis_referenciadas("se(modal == 'X', max(cif * p.a, p.b), aliq.ii)")
    assert refs == {"modal", "cif", "p.a", "p.b", "aliq.ii"}


@pytest.mark.parametrize(
    "expressao",
    [
        "__import__('os').system('dir')",
        "().__class__",
        "cif.__class__",
        "open('x')",
        "lambda: 1",
        "[1, 2]",
        "cif ** 2",
        "x if y else z",
        "p",
        "True",
        "a.b",
        "max(1)",
    ],
)
def test_rejeita_construcoes_nao_permitidas(expressao):
    with pytest.raises(ErroFormula):
        compilar(expressao)


def test_divisao_por_zero():
    with pytest.raises(ErroFormula, match="Divisão por zero"):
        avaliar("1 / (1 - aliq.icms)", {"aliq.icms": D("1")})


def test_parametro_ausente_mensagem_clara():
    with pytest.raises(ErroFormula, match="Parâmetro sem valor vigente: tcif_valor_item"):
        avaliar("p.tcif_valor_item * 2", {})


def test_resultado_deve_ser_numerico():
    with pytest.raises(ErroFormula):
        avaliar("modal", {"modal": "MARITIMO"})
