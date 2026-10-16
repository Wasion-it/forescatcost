from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import Permissoes, exigir
from app.core.json import serializar
from app.models import Importacao, TipoImportacao, Usuario
from app.modules.provisoes import service

router = APIRouter(tags=["Provisões"])

Ler = Annotated[Usuario, Depends(exigir(Permissoes.PROVISAO_LER))]
DB = Annotated[Session, Depends(get_db)]
Visao = Literal["mensal", "por-processo", "por-tipo"]


def _periodo_padrao(de: date | None, ate: date | None) -> tuple[date, date]:
    hoje = date.today().replace(day=1)
    return (de or hoje - relativedelta(months=2), ate or hoje + relativedelta(months=3))


@router.get("/provisoes/{visao}")
def consultar(visao: Visao, db: DB, _: Ler, de: date | None = None, ate: date | None = None,
              tipo: str | None = None):  # fmt: skip
    de, ate = _periodo_padrao(de, ate)
    funcao = service.VISOES[visao][0]
    return serializar(funcao(db, de, ate, tipo))


@router.get("/provisoes/{visao}/excel")
def exportar(visao: Visao, db: DB, usuario: Ler, de: date | None = None, ate: date | None = None,
             tipo: str | None = None):  # fmt: skip
    de, ate = _periodo_padrao(de, ate)
    dados = service.VISOES[visao][0](db, de, ate, tipo)
    tipo_nome = "Todos"
    if tipo:
        tipo_nome = (
            db.scalar(select(TipoImportacao.nome).where(TipoImportacao.codigo == tipo)) or tipo
        )
    filtros = f"competência {de:%m/%Y} a {ate:%m/%Y}; tipo: {tipo_nome}"
    conteudo = service.gerar_excel(visao, dados, filtros, usuario.nome)
    nome = f"provisao-{visao}-{de:%Y%m}-{ate:%Y%m}.xlsx"
    return Response(
        content=conteudo,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/dashboard")
def dashboard(db: DB, _: Ler):
    hoje = date.today().replace(day=1)
    de, ate = hoje - relativedelta(months=6), hoje + relativedelta(months=5)
    competencias = service.meses(de, ate)
    linhas = service.buscar_linhas(db, de, ate)

    serie: dict[str, dict] = {
        m.isoformat(): {
            "competencia": m.isoformat(),
            "por_tipo": defaultdict(Decimal),
            "total": Decimal(0),
        }
        for m in competencias
    }
    composicao: dict[str, Decimal] = defaultdict(Decimal)
    por_tipo: dict[str, dict] = {}
    for ln in linhas:
        ponto = serie[ln.competencia.isoformat()]
        ponto["por_tipo"][ln.tipo_codigo] += ln.valor
        ponto["total"] += ln.valor
        composicao[ln.natureza] += ln.valor
        t = por_tipo.setdefault(
            ln.tipo_codigo, {"codigo": ln.tipo_codigo, "nome": ln.tipo_nome, "valor": Decimal(0)}
        )
        t["valor"] += ln.valor

    data_ref = func.coalesce(Importacao.data_ip, Importacao.data_prevista)
    mes = func.date_trunc("month", data_ref)
    contagem = dict(
        db.execute(
            select(mes, func.count())
            .where(
                Importacao.status != "CANCELADO",
                data_ref >= de,
                data_ref < ate + relativedelta(months=1),
            )
            .group_by(mes)
        ).all()
    )
    importacoes_mes = [
        {
            "mes": m.isoformat(),
            "quantidade": next((q for k, q in contagem.items() if k.date() == m), 0),
        }
        for m in competencias
    ]

    def _conta(*condicoes) -> int:
        return db.scalar(select(func.count()).select_from(Importacao).where(*condicoes)) or 0

    proximo = (hoje + relativedelta(months=1)).isoformat()
    return serializar(
        {
            "competencia_atual": hoje.isoformat(),
            "kpis": {
                "provisao_mes_atual": serie[hoje.isoformat()]["total"],
                "provisao_proximo_mes": serie[proximo]["total"],
                "processos_ativos": _conta(Importacao.status != "CANCELADO"),
                "rascunhos": _conta(Importacao.status == "RASCUNHO"),
                "desatualizados": _conta(
                    Importacao.calculo_desatualizado.is_(True), Importacao.status != "CANCELADO"
                ),
            },
            "serie": [{**p, "por_tipo": dict(p["por_tipo"])} for p in serie.values()],
            "importacoes_por_mes": importacoes_mes,
            "por_tipo": sorted(por_tipo.values(), key=lambda t: t["nome"]),
            "composicao": [{"natureza": k, "valor": v} for k, v in sorted(composicao.items())],
        }
    )
