"""Consolidação das provisões a partir dos cálculos vigentes."""

from __future__ import annotations

import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import xlsxwriter
from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.erros import ErroNegocio
from app.models import Calculo, CalculoItem, Importacao, TipoImportacao

MAX_MESES = 24
ZERO = Decimal(0)


@dataclass
class Linha:
    competencia: date
    codigo: str
    nome: str
    natureza: str
    ordem: int
    valor: Decimal
    importacao_id: str
    numero: int
    numero_declaracao: str | None
    data_referencia: date | None
    tipo_codigo: str
    tipo_nome: str


def meses(de: date, ate: date) -> list[date]:
    de, ate = de.replace(day=1), ate.replace(day=1)
    if ate < de:
        raise ErroNegocio("A competência final deve ser igual ou posterior à inicial")
    lista = []
    atual = de
    while atual <= ate:
        lista.append(atual)
        atual += relativedelta(months=1)
    if len(lista) > MAX_MESES:
        raise ErroNegocio(f"Consulte no máximo {MAX_MESES} meses por vez")
    return lista


def buscar_linhas(db: Session, de: date, ate: date, tipo: str | None = None) -> list[Linha]:
    data_ref = func.coalesce(Importacao.data_declaracao, Importacao.data_prevista)
    consulta = (
        select(
            CalculoItem.competencia,
            CalculoItem.componente_codigo,
            CalculoItem.componente_nome,
            CalculoItem.natureza,
            CalculoItem.ordem,
            CalculoItem.valor,
            Importacao.id,
            Importacao.numero,
            Importacao.numero_declaracao,
            data_ref,
            TipoImportacao.codigo,
            TipoImportacao.nome,
        )
        .join(Calculo, Calculo.id == CalculoItem.calculo_id)
        .join(Importacao, Importacao.id == Calculo.importacao_id)
        .join(TipoImportacao, TipoImportacao.id == Importacao.tipo_importacao_id)
        .where(
            Calculo.vigente.is_(True),
            Importacao.status != "CANCELADO",
            CalculoItem.compoe_provisao.is_(True),
            CalculoItem.competencia >= de.replace(day=1),
            CalculoItem.competencia <= ate.replace(day=1),
        )
    )
    if tipo:
        consulta = consulta.where(TipoImportacao.codigo == tipo)
    return [
        Linha(*[str(c) if i == 6 else c for i, c in enumerate(row)]) for row in db.execute(consulta)
    ]


def _montar(competencias: list[date], grupos: dict[str, dict], linhas: list[Linha], chave, extra):
    for ln in linhas:
        k = chave(ln)
        if k not in grupos:
            grupos[k] = {**extra(ln), "valores": defaultdict(lambda: ZERO), "total": ZERO}
        grupos[k]["valores"][ln.competencia.isoformat()] += ln.valor
        grupos[k]["total"] += ln.valor
    totais = {m.isoformat(): ZERO for m in competencias}
    for ln in linhas:
        totais[ln.competencia.isoformat()] += ln.valor
    saida = []
    for g in grupos.values():
        g["valores"] = {m.isoformat(): g["valores"].get(m.isoformat(), ZERO) for m in competencias}
        saida.append(g)
    return {
        "competencias": [m.isoformat() for m in competencias],
        "linhas": saida,
        "totais": totais,
        "total": sum(totais.values(), ZERO),
    }


def mensal(db: Session, de: date, ate: date, tipo: str | None) -> dict:
    competencias = meses(de, ate)
    linhas = sorted(buscar_linhas(db, de, ate, tipo), key=lambda ln: (ln.ordem, ln.codigo))
    return _montar(
        competencias,
        {},
        linhas,
        chave=lambda ln: ln.codigo,
        extra=lambda ln: {"chave": ln.codigo, "rotulo": ln.nome, "natureza": ln.natureza},
    )


def por_processo(db: Session, de: date, ate: date, tipo: str | None) -> dict:
    competencias = meses(de, ate)
    linhas = sorted(
        buscar_linhas(db, de, ate, tipo),
        key=lambda ln: (ln.data_referencia or date.min, ln.numero),
    )
    resultado = _montar(
        competencias,
        {},
        linhas,
        chave=lambda ln: ln.importacao_id,
        extra=lambda ln: {
            "chave": ln.importacao_id,
            "rotulo": f"IMP-{ln.numero:05d}",
            "numero_declaracao": ln.numero_declaracao,
            "data_referencia": ln.data_referencia.isoformat() if ln.data_referencia else None,
            "tipo_codigo": ln.tipo_codigo,
            "tipo_nome": ln.tipo_nome,
        },
    )
    return resultado


def por_tipo(db: Session, de: date, ate: date, tipo: str | None) -> dict:
    competencias = meses(de, ate)
    linhas = sorted(buscar_linhas(db, de, ate, tipo), key=lambda ln: ln.tipo_nome)
    return _montar(
        competencias,
        {},
        linhas,
        chave=lambda ln: ln.tipo_codigo,
        extra=lambda ln: {"chave": ln.tipo_codigo, "rotulo": ln.tipo_nome},
    )


VISOES = {
    "mensal": (mensal, "Provisão mensal por componente", "Componente"),
    "por-processo": (por_processo, "Provisão por processo (DI)", "Processo"),
    "por-tipo": (por_tipo, "Provisão por tipo de importação", "Tipo de importação"),
}


def _rotulo_mes(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.month:02d}/{d.year}"


def gerar_excel(visao: str, dados: dict, filtros: str, emitido_por: str) -> bytes:
    _, titulo, rotulo_coluna = VISOES[visao]
    buffer = io.BytesIO()
    wb = xlsxwriter.Workbook(buffer, {"in_memory": True})
    ws = wb.add_worksheet("Provisão")

    f_titulo = wb.add_format({"bold": True, "font_size": 14})
    f_info = wb.add_format({"font_color": "#555555"})
    f_cab = wb.add_format(
        {"bold": True, "bg_color": "#1F3A40", "font_color": "#FFFFFF", "border": 1}
    )
    f_cab_num = wb.add_format(
        {
            "bold": True,
            "bg_color": "#1F3A40",
            "font_color": "#FFFFFF",
            "border": 1,
            "align": "right",
        }
    )
    f_moeda = wb.add_format({"num_format": "R$ #,##0.00", "border": 1})
    f_texto = wb.add_format({"border": 1})
    f_total = wb.add_format({"bold": True, "num_format": "R$ #,##0.00", "top": 2, "border": 1})
    f_total_txt = wb.add_format({"bold": True, "top": 2, "border": 1})

    ws.write(0, 0, titulo, f_titulo)
    ws.write(1, 0, f"Filtros: {filtros}", f_info)
    ws.write(2, 0, f"Emitido em {datetime.now():%d/%m/%Y %H:%M} por {emitido_por}", f_info)

    extras: list[tuple[str, str]] = []
    if visao == "por-processo":
        extras = [
            ("numero_declaracao", "DI/DUIMP"),
            ("data_referencia", "Data"),
            ("tipo_nome", "Tipo"),
        ]

    linha = 4
    cabecalho = [rotulo_coluna, *[e[1] for e in extras]]
    for col, texto in enumerate(cabecalho):
        ws.write(linha, col, texto, f_cab)
    base_col = len(cabecalho)
    for i, comp in enumerate(dados["competencias"]):
        ws.write(linha, base_col + i, _rotulo_mes(comp), f_cab_num)
    col_total = base_col + len(dados["competencias"])
    ws.write(linha, col_total, "Total", f_cab_num)

    for item in dados["linhas"]:
        linha += 1
        ws.write(linha, 0, item["rotulo"], f_texto)
        for j, (campo, _) in enumerate(extras, start=1):
            valor = item.get(campo) or ""
            if campo == "data_referencia" and valor:
                valor = date.fromisoformat(valor).strftime("%d/%m/%Y")
            ws.write(linha, j, valor, f_texto)
        for i, comp in enumerate(dados["competencias"]):
            ws.write_number(linha, base_col + i, float(item["valores"][comp]), f_moeda)
        ws.write_number(linha, col_total, float(item["total"]), f_moeda)

    linha += 1
    ws.write(linha, 0, "Total", f_total_txt)
    for j in range(1, base_col):
        ws.write(linha, j, "", f_total_txt)
    for i, comp in enumerate(dados["competencias"]):
        ws.write_number(linha, base_col + i, float(dados["totais"][comp]), f_total)
    ws.write_number(linha, col_total, float(dados["total"]), f_total)

    ws.set_column(0, 0, 34)
    ws.set_column(1, base_col - 1, 16)
    ws.set_column(base_col, col_total, 16)
    ws.freeze_panes(5, 1)
    wb.close()
    return buffer.getvalue()
