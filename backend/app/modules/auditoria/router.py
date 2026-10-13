from datetime import date, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import Permissoes, exigir
from app.models import Auditoria, Usuario

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])
DB = Annotated[Session, Depends(get_db)]
Ler = Annotated[Usuario, Depends(exigir(Permissoes.AUDITORIA_LER))]


@router.get("")
def consultar(
    db: DB,
    _: Ler,
    tabela: str | None = None,
    registro_id: str | None = None,
    usuario_id: UUID | None = None,
    de: date | None = None,
    ate: date | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=200)] = 50,
):
    consulta = select(Auditoria, Usuario.nome).outerjoin(
        Usuario, Usuario.id == Auditoria.usuario_id
    )
    if tabela:
        consulta = consulta.where(Auditoria.tabela == tabela)
    if registro_id:
        consulta = consulta.where(Auditoria.registro_id == registro_id)
    if usuario_id:
        consulta = consulta.where(Auditoria.usuario_id == usuario_id)
    if de:
        consulta = consulta.where(Auditoria.ocorrido_em >= de)
    if ate:
        consulta = consulta.where(Auditoria.ocorrido_em < ate + timedelta(days=1))
    total = db.scalar(select(func.count()).select_from(consulta.subquery())) or 0
    linhas = db.execute(
        consulta.order_by(Auditoria.id.desc()).offset((pagina - 1) * tamanho).limit(tamanho)
    ).all()
    return {
        "total": total,
        "pagina": pagina,
        "tamanho": tamanho,
        "itens": [
            {
                "id": a.id,
                "tabela": a.tabela,
                "registro_id": a.registro_id,
                "acao": a.acao,
                "campos_alterados": a.campos_alterados,
                "dados_antes": a.dados_antes,
                "dados_depois": a.dados_depois,
                "usuario_nome": nome or "Sistema",
                "ocorrido_em": a.ocorrido_em,
            }
            for a, nome in linhas
        ],
    }


@router.get("/tabelas")
def tabelas(db: DB, _: Ler):
    return db.scalars(select(Auditoria.tabela).distinct().order_by(Auditoria.tabela)).all()
