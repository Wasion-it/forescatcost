"""Componentes de custo e fórmulas da versão 1 (docs/04-motor-de-calculo.md).

Fonte única usada pelo seed e pelos testes do motor.
"""

from app.calculo.engine import Componente, RegraCompetencia

R = RegraCompetencia

COMPONENTES_PADRAO: list[Componente] = [
    Componente("CIF", "CIF", "invoice_brl + frete_brl + siscomex", False, R.MES_REFERENCIA, 10),
    Componente("II", "Imposto de Importação", "cif * aliq.ii", True, R.MES_REFERENCIA, 20),
    Componente("IPI", "IPI", "(cif + ii) * aliq.ipi", True, R.MES_REFERENCIA, 30),
    Componente("PIS", "PIS importação", "cif * aliq.pis", True, R.MES_REFERENCIA, 40),
    Componente("COFINS", "COFINS importação", "cif * aliq.cofins", True, R.MES_REFERENCIA, 50),
    Componente(
        "AFRMM",
        "AFRMM",
        "se(modal == 'MARITIMO', frete_brl * p.afrmm_percentual, 0)",
        True,
        R.MES_REFERENCIA,
        60,
    ),
    Componente(
        "ICMS",
        "ICMS",
        "(cif + ii + ipi + pis + cofins + afrmm) / (1 - aliq.icms) * aliq.icms",
        True,
        R.MES_REFERENCIA,
        70,
    ),
    Componente(
        "TCIF",
        "TCIF (SUFRAMA)",
        "qtd_itens * p.tcif_valor_item + p.tcif_valor_di",
        True,
        R.CORTE_DIA,
        80,
    ),
    Componente(
        "TRANSP_LOCAL",
        "Transporte local",
        "qtd_containers * p.tl_valor_container + valor_carga * p.tl_percentual",
        True,
        R.MES_REFERENCIA,
        90,
    ),
    Componente(
        "TRANSP_SEC",
        "Transporte secundário",
        "qtd_containers * p.ts_valor_container + valor_carga * p.ts_percentual",
        True,
        R.MES_REFERENCIA,
        100,
    ),
    Componente(
        "ARM_MARITIMA",
        "Armazenagem marítima",
        "se(modal == 'MARITIMO', max(cif * p.arm_mar_pct_periodo1, p.arm_mar_minimo), 0)",
        True,
        R.MES_REFERENCIA,
        110,
    ),
    Componente(
        "ARM_AEREA",
        "Armazenagem aérea",
        "se(modal == 'AEREO', arm_aerea_manual, 0)",
        True,
        R.MES_REFERENCIA,
        120,
    ),
    Componente(
        "DESPACHANTE",
        "Despachante",
        "p.despachante_honorario_di",
        True,
        R.MES_REFERENCIA,
        130,
    ),
    Componente(
        "FRETE_INTL",
        "Frete internacional + liberação",
        "frete_brl + p.taxa_liberacao",
        True,
        R.MES_REFERENCIA,
        140,
    ),
]
