from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from app.calculo.engine import (
    Componente,
    Entradas,
    ErroCalculo,
    RegraCompetencia,
    calcular,
    competencia,
)
from app.calculo.formulas_padrao import COMPONENTES_PADRAO

D = Decimal

PARAMETROS = {
    "afrmm_percentual": D("0.08"),
    "tcif_valor_item": D("45"),
    "tcif_valor_di": D("245"),
    "tl_valor_container": D("1500"),
    "tl_percentual": D("0.0006"),
    "ts_valor_container": D("1000"),
    "ts_percentual": D("0.0001"),
    "arm_mar_pct_periodo1": D("0.0092"),
    "arm_mar_minimo": D("0"),
    "despachante_honorario_di": D("900"),
    "taxa_liberacao": D("350"),
}
ALIQUOTAS = {
    "II": D("0.14"),
    "IPI": D("0.10"),
    "PIS": D("0.021"),
    "COFINS": D("0.0965"),
    "ICMS": D("0.18"),
}

ENTRADAS = Entradas(
    data_referencia=date(2026, 10, 16),
    tipo_importacao="USO_CONSUMO",
    modal="MARITIMO",
    valor_invoice=D("10000"),
    moeda_invoice="USD",
    valor_frete=D("2000"),
    moeda_frete="USD",
    qtd_itens=10,
    qtd_containers=2,
    taxa_usd=D("5.00"),
    taxa_cny=None,
    valor_siscomex=D("154.23"),
    peso_bruto=D("12000"),
    peso_liquido=D("11000"),
)


def test_caso_referencia_maritimo_uso_consumo():
    """Caso calculado à mão (ver comentários) — serve como golden test inicial."""
    r = calcular(ENTRADAS, COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS).por_codigo()
    esperado = {
        "CIF": "60154.23",  # 50.000 + 10.000 + 154,23
        "II": "8421.59",  # 60.154,23 × 14%
        "IPI": "6857.58",  # (CIF + II) × 10%
        "PIS": "1263.24",
        "COFINS": "5804.88",
        "AFRMM": "800.00",  # 10.000 × 8%
        "ICMS": "18285.70",  # 83.301,52 / 0,82 × 0,18
        "TCIF": "695.00",  # 10 × 45 + 245
        "TRANSP_LOCAL": "3036.09",  # 2 × 1.500 + 0,06% × CIF
        "TRANSP_SEC": "2006.02",  # 2 × 1.000 + 0,01% × CIF
        "ARM_MARITIMA": "553.42",  # 0,92% × CIF
        "ARM_AEREA": "0.00",
        "DESPACHANTE": "900.00",
        "FRETE_INTL": "10350.00",
    }
    assert {k: str(v.valor) for k, v in r.items()} == esperado


def test_total_ignora_cif_base():
    resultado = calcular(ENTRADAS, COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS)
    assert resultado.total_provisionado == D("58973.52")


def test_tcif_competencia_mes_seguinte_apos_dia_15():
    r = calcular(ENTRADAS, COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS).por_codigo()
    assert r["TCIF"].competencia == date(2026, 11, 1)
    assert r["II"].competencia == date(2026, 10, 1)


@pytest.mark.parametrize(
    ("data", "esperado"),
    [
        (date(2026, 10, 15), date(2026, 10, 1)),
        (date(2026, 10, 16), date(2026, 11, 1)),
        (date(2026, 10, 1), date(2026, 10, 1)),
        (date(2026, 12, 20), date(2027, 1, 1)),
        (date(2026, 1, 31), date(2026, 2, 1)),
    ],
)
def test_regra_corte_dia(data, esperado):
    assert competencia(data, RegraCompetencia.CORTE_DIA, 15) == esperado


def test_conversao_cny():
    entradas = replace(
        ENTRADAS, moeda_invoice="CNY", valor_invoice=D("100000"), taxa_cny=D("0.7512")
    )
    r = calcular(entradas, COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS)
    assert r.variaveis_base["invoice_brl"] == "75120.00"


def test_moeda_sem_taxa():
    entradas = replace(ENTRADAS, moeda_invoice="CNY", taxa_cny=None)
    with pytest.raises(ErroCalculo, match="CNY"):
        calcular(entradas, COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS)


def test_modal_aereo_usa_valor_manual_e_zera_maritimos():
    entradas = replace(ENTRADAS, modal="AEREO", valor_armazenagem_aerea=D("1234.56"))
    r = calcular(entradas, COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS).por_codigo()
    assert r["ARM_AEREA"].valor == D("1234.56")
    assert r["ARM_MARITIMA"].valor == 0
    assert r["AFRMM"].valor == 0


def test_parametro_ausente_lista_problema():
    parametros = {k: v for k, v in PARAMETROS.items() if k != "tcif_valor_item"}
    with pytest.raises(ErroCalculo) as exc:
        calcular(ENTRADAS, COMPONENTES_PADRAO, parametros, ALIQUOTAS)
    assert any("tcif_valor_item" in p for p in exc.value.problemas)


def test_dependencia_circular_e_rejeitada():
    comps = [
        Componente("A", "A", "b + 1", True, RegraCompetencia.MES_REFERENCIA),
        Componente("B", "B", "a + 1", True, RegraCompetencia.MES_REFERENCIA),
    ]
    with pytest.raises(ErroCalculo, match="circular"):
        calcular(ENTRADAS, comps, {}, {})


def test_memoria_registra_variaveis_usadas():
    r = calcular(ENTRADAS, COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS).por_codigo()
    assert r["II"].variaveis == {"aliq.ii": "0.14", "cif": "60154.23"}


def test_mais_containers_nao_reduz_custo():
    base = calcular(ENTRADAS, COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS).total_provisionado
    mais = calcular(
        replace(ENTRADAS, qtd_containers=3), COMPONENTES_PADRAO, PARAMETROS, ALIQUOTAS
    ).total_provisionado
    assert mais > base
