from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import Permissoes, exigir
from app.core.erros import ErroNegocio
from app.models import Calculo, Usuario
from app.modules.calculo import service as calculo_service
from app.modules.importacoes import service
from app.modules.importacoes.schemas import (
    CalculoResumo,
    CalculoSaida,
    Cancelamento,
    ImportacaoAtualizacao,
    ImportacaoDetalhe,
    ImportacaoEntrada,
    Pagina,
    PreviaSaida,
    RegistroCalculo,
)

router = APIRouter(prefix="/importacoes", tags=["Importações"])

Ler = Annotated[Usuario, Depends(exigir(Permissoes.IMPORTACAO_LER))]
Editar = Annotated[Usuario, Depends(exigir(Permissoes.IMPORTACAO_EDITAR))]
Calcular = Annotated[Usuario, Depends(exigir(Permissoes.CALCULO_EXECUTAR))]
DB = Annotated[Session, Depends(get_db)]


def _detalhe(db: Session, imp) -> ImportacaoDetalhe:
    vigente = calculo_service.calculo_vigente(db, imp.id)
    detalhe = ImportacaoDetalhe.model_validate(imp)
    if vigente:
        detalhe.calculo_vigente = CalculoSaida.model_validate(calculo_service.para_saida(vigente))
    return detalhe


@router.get("", response_model=Pagina)
def listar(
    db: DB,
    _: Ler,
    q: str | None = None,
    tipo: str | None = None,
    status_: Annotated[
        Literal["RASCUNHO", "CALCULADO", "CANCELADO", "DESATUALIZADO"] | None,
        Query(alias="status"),
    ] = None,
    de: date | None = None,
    ate: date | None = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    tamanho: Annotated[int, Query(ge=1, le=200)] = 25,
):
    consulta = service.consulta_lista(q, tipo, status_, de, ate)
    total = db.scalar(select(func.count()).select_from(consulta.order_by(None).subquery()))
    linhas = db.execute(consulta.offset((pagina - 1) * tamanho).limit(tamanho)).all()
    itens = [
        {
            "id": imp.id,
            "numero_processo": imp.numero_processo,
            "numero_ip": imp.numero_ip,
            "data_referencia": imp.data_referencia,
            "data_ip": imp.data_ip,
            "tipo_importacao": imp.tipo_importacao,
            "modal": imp.modal,
            "status": imp.status,
            "calculo_desatualizado": imp.calculo_desatualizado,
            "total_provisionado": total_prov,
            "atualizado_em": imp.atualizado_em,
        }
        for imp, total_prov in linhas
    ]
    return {"itens": itens, "total": total or 0, "pagina": pagina, "tamanho": tamanho}


@router.post("", response_model=ImportacaoDetalhe, status_code=status.HTTP_201_CREATED)
def criar(dados: ImportacaoEntrada, db: DB, usuario: Editar):
    imp = service.criar(db, dados, usuario)
    db.commit()
    return _detalhe(db, imp)


@router.get("/{importacao_id}", response_model=ImportacaoDetalhe)
def detalhar(importacao_id: UUID, db: DB, _: Ler):
    return _detalhe(db, service.obter(db, importacao_id))


@router.put("/{importacao_id}", response_model=ImportacaoDetalhe)
def atualizar(importacao_id: UUID, dados: ImportacaoAtualizacao, db: DB, _: Editar):
    imp = service.atualizar(db, service.obter(db, importacao_id), dados)
    db.commit()
    return _detalhe(db, imp)


@router.post("/{importacao_id}/cancelar", response_model=ImportacaoDetalhe)
def cancelar(importacao_id: UUID, dados: Cancelamento, db: DB, _: Editar):
    imp = service.cancelar(db, service.obter(db, importacao_id), dados.motivo)
    db.commit()
    return _detalhe(db, imp)


@router.post("/{importacao_id}/calculos/previa", response_model=PreviaSaida)
def previa(importacao_id: UUID, db: DB, _: Calcular):
    return calculo_service.previa(db, service.obter(db, importacao_id))


@router.post(
    "/{importacao_id}/calculos", response_model=CalculoSaida, status_code=status.HTTP_201_CREATED
)
def registrar_calculo(importacao_id: UUID, dados: RegistroCalculo, db: DB, usuario: Calcular):
    imp = service.obter(db, importacao_id)
    calculo = calculo_service.registrar(db, imp, dados.motivo, usuario)
    db.commit()
    return calculo_service.para_saida(calculo)


@router.get("/{importacao_id}/calculos", response_model=list[CalculoResumo])
def historico(importacao_id: UUID, db: DB, _: Ler):
    service.obter(db, importacao_id)
    calculos = db.scalars(
        select(Calculo)
        .where(Calculo.importacao_id == importacao_id)
        .order_by(Calculo.numero_versao.desc())
    ).all()
    return [calculo_service.para_saida(c) for c in calculos]


@router.get("/{importacao_id}/calculos/{calculo_id}", response_model=CalculoSaida)
def obter_calculo(importacao_id: UUID, calculo_id: UUID, db: DB, _: Ler):
    calculo = db.get(Calculo, calculo_id)
    if calculo is None or calculo.importacao_id != importacao_id:
        raise ErroNegocio("Cálculo não encontrado", status=404)
    return calculo_service.para_saida(calculo)
