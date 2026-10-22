"""Componentes de custo e fórmulas da versão 1 (docs/04-motor-de-calculo.md).

Fonte única usada pelo seed e pelos testes do motor.
"""

from app.calculo.engine import Componente, RegraCompetencia

R = RegraCompetencia

# Taxa de utilização do Siscomex (Portaria ME 4.131/2021): valor por DI/Duimp mais um valor
# por adição, decrescente por faixa (1ª-2ª, 3ª-5ª, 6ª-10ª, 11ª-20ª, 21ª-50ª, 51ª em diante).
# Como é provisão, o nº de adições ainda não existe: usa-se qtd_itens como estimativa
# (adições ≤ itens, então a estimativa é conservadora). Se o usuário informar o valor real
# (`siscomex` > 0), ele prevalece sobre o cálculo.
FORMULA_TAXA_SISCOMEX = (
    "se(siscomex > 0, siscomex, "
    "p.siscomex_registro "
    "+ min(qtd_itens, 2) * p.siscomex_adicao_faixa1 "
    "+ max(min(qtd_itens, 5) - 2, 0) * p.siscomex_adicao_faixa2 "
    "+ max(min(qtd_itens, 10) - 5, 0) * p.siscomex_adicao_faixa3 "
    "+ max(min(qtd_itens, 20) - 10, 0) * p.siscomex_adicao_faixa4 "
    "+ max(min(qtd_itens, 50) - 20, 0) * p.siscomex_adicao_faixa5 "
    "+ max(qtd_itens - 50, 0) * p.siscomex_adicao_faixa6)"
)
# CIF = valor aduaneiro (FOB + frete), como na DI. A Taxa Siscomex não integra o valor aduaneiro:
# fica fora da base de II, IPI, PIS, COFINS, armazenagem e transporte, e entra só na base do ICMS.
FORMULA_CIF = "invoice_brl + frete_brl"
FORMULA_ICMS = "(cif + taxa_siscomex + ii + ipi + pis + cofins) / (1 - aliq.icms) * aliq.icms"

# Armazenagem marítima, 1º período (planilha "Cálculo Armazenagem", aba Custos Marítimos):
# percentual do CIF, mais os serviços portuários por container (arm_mar_taxas_container, usado
# pela Santos Brasil) e os serviços portuários fixos por processo do terminal (pesagem,
# infraestrutura, ISPS, seguro, inspeção e serviços administrativos; Chibatão e Superterminais),
# que não multiplicam por container. Os terminais que embutem PIS/COFINS + ISS nas tarifas
# (ex.: Santos Brasil, 14,25%) usam arm_mar_pct_impostos para o gross-up (valor / (1 - %)); nos
# demais o parâmetro é 0. Períodos seguintes não entram na provisão ("valor extra" na planilha).
FORMULA_ARM_MARITIMA = (
    "se(modal == 'MARITIMO', "
    "max((cif * p.arm_mar_pct_periodo1 + qtd_containers * p.arm_mar_taxas_container "
    "+ p.arm_mar_pesagem + p.arm_mar_infra + p.arm_mar_isps + p.arm_mar_seguro "
    "+ p.arm_mar_inspecao + p.arm_mar_servicos_adm) "
    "/ (1 - p.arm_mar_pct_impostos), p.arm_mar_minimo), 0)"
)
# Armazenagem aérea (aba Custos Aéreos): percentual do CIF mais a tarifa por kg de peso bruto,
# respeitado o mínimo da tarifa de peso. Se o usuário informar o valor no processo, ele prevalece.
FORMULA_ARM_AEREA = (
    "se(modal == 'AEREO', "
    "se(arm_aerea_manual > 0, arm_aerea_manual, "
    "cif * p.arm_aer_pct + max(peso_bruto * p.arm_aer_taxa_kg, p.arm_aer_minimo_peso)), 0)"
)

COMPONENTES_PADRAO: list[Componente] = [
    Componente("CIF", "CIF", FORMULA_CIF, False, R.MES_REFERENCIA, 10),
    Componente(
        "II",
        "Imposto de Importação",
        "se(p.ii_suspenso == 1, 0, cif * aliq.ii)",
        True,
        R.MES_REFERENCIA,
        20,
    ),
    Componente(
        "IPI",
        "IPI",
        "se(p.ipi_suspenso == 1, 0, (cif + ii) * aliq.ipi)",
        True,
        R.MES_REFERENCIA,
        30,
    ),
    Componente("PIS", "PIS importação", "cif * aliq.pis", True, R.MES_REFERENCIA, 40),
    Componente("COFINS", "COFINS importação", "cif * aliq.cofins", True, R.MES_REFERENCIA, 50),
    Componente("TAXA_SISCOMEX", "Taxa Siscomex", FORMULA_TAXA_SISCOMEX, True, R.MES_REFERENCIA, 60),
    Componente("ICMS", "ICMS", FORMULA_ICMS, True, R.MES_REFERENCIA, 70),
    Componente(
        "TCIF",
        "TCIF (SUFRAMA)",
        "qtd_itens * p.tcif_valor_item + p.tcif_valor_ip",
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
        "ARM_MARITIMA",
        "Armazenagem marítima",
        FORMULA_ARM_MARITIMA,
        True,
        R.MES_REFERENCIA,
        110,
    ),
    Componente(
        "ARM_AEREA",
        "Armazenagem aérea",
        FORMULA_ARM_AEREA,
        True,
        R.MES_REFERENCIA,
        120,
    ),
    Componente(
        "DESPACHANTE",
        "Despachante",
        "p.despachante_honorario_ip",
        True,
        R.MES_REFERENCIA,
        130,
    ),
    Componente(
        "FRETE_INTL",
        "Frete internacional",
        "frete_brl",
        True,
        R.MES_REFERENCIA,
        140,
    ),
    Componente(
        "TAXA_LIBERACAO",
        "Taxa de liberação",
        "valor_taxa_liberacao",
        True,
        R.MES_REFERENCIA,
        150,
    ),
]
