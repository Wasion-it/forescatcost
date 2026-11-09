"""Planilha da provisão de um processo: cada item da despesa separado, com a margem de 20%.

Exporta em qualquer situação com cálculo vigente (calculado, com despesa parcial ou fechada,
cancelado). Itens já fechados trazem a fatura e o realizado; os demais aparecem como pendentes.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

import xlsxwriter

from app.models import Calculo, Importacao
from app.modules.importacoes.schemas import DespesaFechada

# Margem de segurança ("gordura") sobre o provisionado, aplicada item a item, para a fatura não
# exigir nova aprovação se vier um pouco acima. Mesmo valor de frontend/src/lib/margem.ts.
MARGEM_PROVISAO_PCT = 20

GRUPOS = [
    ("IMPOSTO", "Impostos"),
    ("TAXA", "Taxas"),
    ("LOGISTICA", "Frete, transporte e armazenagem"),
    ("SERVICO", "Serviços"),
]

STATUS = {
    "RASCUNHO": "Rascunho",
    "CALCULADO": "Calculado",
    "FECHADO": "Fechado",
    "CANCELADO": "Cancelado",
}

CENTAVO = Decimal("0.01")

# Horário de Manaus (UTC−4, sem horário de verão), independente do fuso do servidor
FUSO = timezone(timedelta(hours=-4), "Manaus")


def com_margem(valor: Decimal) -> Decimal:
    """Provisionado + margem, arredondado a centavos."""
    return (valor * (100 + MARGEM_PROVISAO_PCT) / 100).quantize(CENTAVO, ROUND_HALF_UP)


def _data(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "–"


def gerar_excel(
    imp: Importacao,
    calculo: Calculo,
    fechadas: list[DespesaFechada],
    emitido_por: str,
) -> bytes:
    buffer = io.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True})
    ws = wb.add_worksheet("Provisão")

    cor_cab = "#1F3A40"
    f_titulo = wb.add_format({"bold": True, "font_size": 14})
    f_rotulo = wb.add_format({"font_color": "#555555"})
    f_info = wb.add_format({})
    f_cab = wb.add_format({"bold": True, "bg_color": cor_cab, "font_color": "#FFFFFF", "border": 1})
    f_cab_num = wb.add_format(
        {"bold": True, "bg_color": cor_cab, "font_color": "#FFFFFF", "border": 1, "align": "right"}
    )
    f_grupo = wb.add_format({"bold": True, "bg_color": "#EEF0EA", "border": 1})
    f_grupo_moeda = wb.add_format(
        {"bold": True, "bg_color": "#EEF0EA", "border": 1, "num_format": "R$ #,##0.00"}
    )
    f_texto = wb.add_format({"border": 1})
    f_moeda = wb.add_format({"num_format": "R$ #,##0.00", "border": 1})
    f_dif = wb.add_format({"num_format": "+R$ #,##0.00;-R$ #,##0.00;R$ 0,00", "border": 1})
    f_total_txt = wb.add_format({"bold": True, "top": 2, "border": 1})
    f_total = wb.add_format({"bold": True, "num_format": "R$ #,##0.00", "top": 2, "border": 1})

    ws.write(0, 0, f"Provisão do processo {imp.numero_processo}", f_titulo)
    base = [i for i in calculo.itens if not i.compoe_provisao]
    calculado_em = calculo.calculado_em.astimezone(FUSO)
    info = [
        ("IP", imp.numero_ip or "IP ainda não gerada"),
        ("Número da invoice", imp.numero_invoice or "–"),
        ("Tipo de importação", imp.tipo_importacao.nome),
        ("Modal", "Marítimo" if imp.modal == "MARITIMO" else "Aéreo"),
        ("Data da IP", _data(imp.data_ip)),
        ("Data prevista", _data(imp.data_prevista)),
        ("Situação", STATUS.get(imp.status, imp.status)),
        (
            "Cálculo",
            f"versão {calculo.numero_versao}, de {calculado_em:%d/%m/%Y %H:%M}"
            + (f" por {calculo.usuario.nome}" if calculo.usuario else ""),
        ),
        *[(f"{i.componente_nome} (base de cálculo)", i.valor) for i in base],
        ("Margem sobre o provisionado", f"{MARGEM_PROVISAO_PCT}% em cada item"),
        ("Emitido em", f"{datetime.now(UTC).astimezone(FUSO):%d/%m/%Y %H:%M} por {emitido_por}"),
    ]
    linha = 2
    for rotulo, valor in info:
        ws.write(linha, 0, rotulo, f_rotulo)
        if isinstance(valor, Decimal):
            ws.write_number(linha, 1, float(valor), wb.add_format({"num_format": "R$ #,##0.00"}))
        else:
            ws.write(linha, 1, valor, f_info)
        linha += 1

    linha += 1
    cabecalho = [
        ("Item", f_cab),
        ("Competência", f_cab),
        ("Provisionado", f_cab_num),
        (f"Provisionado + {MARGEM_PROVISAO_PCT}%", f_cab_num),
        ("Situação", f_cab),
        ("Nº da fatura", f_cab),
        ("Realizado", f_cab_num),
        ("Diferença (realizado − provisionado)", f_cab_num),
    ]
    for col, (texto, fmt) in enumerate(cabecalho):
        ws.write(linha, col, texto, fmt)
    linha_cabecalho = linha

    por_codigo = {d.componente_codigo: d for d in fechadas}
    total_prov = total_margem = total_real = Decimal(0)
    for natureza, titulo in GRUPOS:
        itens = [i for i in calculo.itens if i.compoe_provisao and i.natureza == natureza]
        if not itens:
            continue
        sub_prov = sum((i.valor for i in itens), Decimal(0))
        sub_margem = sum((com_margem(i.valor) for i in itens), Decimal(0))
        linha += 1
        ws.write(linha, 0, titulo, f_grupo)
        ws.write(linha, 1, "", f_grupo)
        ws.write_number(linha, 2, float(sub_prov), f_grupo_moeda)
        ws.write_number(linha, 3, float(sub_margem), f_grupo_moeda)
        for col in range(4, 8):
            ws.write(linha, col, "", f_grupo)
        for item in sorted(itens, key=lambda i: i.ordem):
            linha += 1
            nome = item.componente_nome
            if item.memoria.get("suspenso"):
                nome += " (suspenso)"
            ws.write(linha, 0, nome, f_texto)
            ws.write(linha, 1, f"{item.competencia:%m/%Y}", f_texto)
            ws.write_number(linha, 2, float(item.valor), f_moeda)
            ws.write_number(linha, 3, float(com_margem(item.valor)), f_moeda)
            fechada = por_codigo.get(item.componente_codigo)
            if fechada:
                ws.write(linha, 4, "Fechada", f_texto)
                ws.write(linha, 5, fechada.numero_fatura, f_texto)
                ws.write_number(linha, 6, float(fechada.valor), f_moeda)
                ws.write_number(linha, 7, float(fechada.valor - item.valor), f_dif)
                total_real += fechada.valor
            else:
                ws.write(linha, 4, "Pendente", f_texto)
                for col in range(5, 8):
                    ws.write(linha, col, "", f_texto)
        total_prov += sub_prov
        total_margem += sub_margem

    linha += 1
    ws.write(linha, 0, "Total", f_total_txt)
    ws.write(linha, 1, "", f_total_txt)
    ws.write_number(linha, 2, float(total_prov), f_total)
    ws.write_number(linha, 3, float(total_margem), f_total)
    pendentes = sum(
        1 for i in calculo.itens if i.compoe_provisao and i.componente_codigo not in por_codigo
    )
    ws.write(linha, 4, f"{pendentes} pendente(s)" if fechadas and pendentes else "", f_total_txt)
    ws.write(linha, 5, "", f_total_txt)
    if fechadas:
        ws.write_number(linha, 6, float(total_real), f_total)
    else:
        ws.write(linha, 6, "", f_total_txt)
    ws.write(linha, 7, "", f_total_txt)

    ws.set_column(0, 0, 38)
    ws.set_column(1, 1, 22)
    ws.set_column(2, 3, 20)
    ws.set_column(4, 5, 16)
    ws.set_column(6, 7, 20)
    ws.freeze_panes(linha_cabecalho + 1, 1)
    wb.close()
    return buffer.getvalue()
