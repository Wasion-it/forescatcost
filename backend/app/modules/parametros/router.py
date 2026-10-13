from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import Permissoes, exigir
from app.core.erros import ErroNegocio
from app.models import (
    Aliquota,
    ComponenteCusto,
    Despachante,
    Imposto,
    Parametro,
    Terminal,
    TipoImportacao,
    Transportadora,
    Usuario,
)
from app.modules.parametros import service

router = APIRouter(tags=["Parâmetros"])
DB = Annotated[Session, Depends(get_db)]
Ler = Annotated[Usuario, Depends(exigir(Permissoes.PARAMETRO_LER))]
Editar = Annotated[Usuario, Depends(exigir(Permissoes.PARAMETRO_EDITAR))]


class VigenciaSaida(BaseModel):
    id: UUID
    valor: Decimal
    vigencia_inicio: date
    vigencia_fim: date | None
    justificativa: str
    criado_por_nome: str | None
    criado_em: datetime
    vigente: bool


class GrupoEscopo(BaseModel):
    escopo_ref_id: UUID | None
    escopo_ref_nome: str
    vigente: VigenciaSaida | None
    historico: list[VigenciaSaida]


class ParametroSaida(BaseModel):
    id: UUID
    chave: str
    descricao: str
    tipo_valor: str
    escopo: str
    grupo: str
    valores: list[GrupoEscopo]


class NovaVigencia(BaseModel):
    escopo_ref_id: UUID | None = None
    valor: Decimal = Field(max_digits=18, decimal_places=6)
    vigencia_inicio: date
    justificativa: str = Field(min_length=5, max_length=300)


class NovaAliquota(BaseModel):
    imposto_id: UUID
    tipo_importacao_id: UUID
    percentual: Decimal = Field(ge=0, lt=1, max_digits=9, decimal_places=6)
    vigencia_inicio: date
    origem: Literal["MANUAL", "TECWIN"] = "MANUAL"
    justificativa: str = Field(min_length=5, max_length=300)


def _nomes_escopo(db: Session) -> dict[UUID, str]:
    nomes: dict[UUID, str] = {}
    for modelo in (TipoImportacao, Transportadora, Despachante, Terminal):
        for obj in db.scalars(select(modelo)):
            nomes[obj.id] = obj.nome
    return nomes


def _usuarios(db: Session) -> dict[UUID, str]:
    return {u.id: u.nome for u in db.scalars(select(Usuario))}


def _vigencia(v, hoje: date, usuarios: dict[UUID, str]) -> VigenciaSaida:
    valor = v.valor if hasattr(v, "valor") else v.percentual
    return VigenciaSaida(
        id=v.id,
        valor=valor,
        vigencia_inicio=v.vigencia_inicio,
        vigencia_fim=v.vigencia_fim,
        justificativa=v.justificativa,
        criado_por_nome=usuarios.get(v.criado_por) if v.criado_por else "Carga inicial",
        criado_em=v.criado_em,
        vigente=v.vigencia_inicio <= hoje and (v.vigencia_fim is None or v.vigencia_fim >= hoje),
    )


@router.get("/parametros", response_model=list[ParametroSaida])
def listar_parametros(db: DB, _: Ler):
    hoje = date.today()
    nomes = _nomes_escopo(db)
    usuarios = _usuarios(db)
    saida = []
    for p in db.scalars(select(Parametro).order_by(Parametro.grupo, Parametro.chave)):
        grupos: dict[UUID | None, list] = {}
        for v in p.valores:
            grupos.setdefault(v.escopo_ref_id, []).append(v)
        valores = []
        for ref, lista in grupos.items():
            hist = [_vigencia(v, hoje, usuarios) for v in lista]
            valores.append(
                GrupoEscopo(
                    escopo_ref_id=ref,
                    escopo_ref_nome="Padrão" if ref is None else nomes.get(ref, "Removido"),
                    vigente=next((h for h in hist if h.vigente), None),
                    historico=hist,
                )
            )
        valores.sort(key=lambda g: (g.escopo_ref_id is not None, g.escopo_ref_nome))
        saida.append(
            ParametroSaida(
                id=p.id,
                chave=p.chave,
                descricao=p.descricao,
                tipo_valor=p.tipo_valor,
                escopo=p.escopo,
                grupo=p.grupo,
                valores=valores,
            )  # fmt: skip
        )
    return saida


@router.post("/parametros/{parametro_id}/vigencias", status_code=status.HTTP_201_CREATED)
def nova_vigencia(parametro_id: UUID, dados: NovaVigencia, db: DB, usuario: Editar):
    parametro = db.get(Parametro, parametro_id)
    if parametro is None:
        raise ErroNegocio("Parâmetro não encontrado", status=404)
    novo = service.nova_vigencia_parametro(
        db, parametro, dados.escopo_ref_id, dados.valor, dados.vigencia_inicio,
        dados.justificativa, usuario.id,
    )  # fmt: skip
    db.commit()
    return {"id": novo.id}


@router.get("/aliquotas")
def listar_aliquotas(db: DB, _: Ler):
    hoje = date.today()
    usuarios = _usuarios(db)
    impostos = db.scalars(
        select(Imposto).where(Imposto.ativo.is_(True)).order_by(Imposto.codigo)
    ).all()
    tipos = db.scalars(select(TipoImportacao).order_by(TipoImportacao.nome)).all()
    todas = db.scalars(select(Aliquota).order_by(Aliquota.vigencia_inicio.desc())).all()
    linhas = []
    for imp in impostos:
        por_tipo = {}
        for t in tipos:
            hist = [
                _vigencia(a, hoje, usuarios)
                for a in todas
                if a.imposto_id == imp.id and a.tipo_importacao_id == t.id
            ]
            origem = next(
                (
                    a.origem
                    for a in todas
                    if a.imposto_id == imp.id and a.tipo_importacao_id == t.id
                ),
                None,
            )
            por_tipo[str(t.id)] = {
                "vigente": next((h for h in hist if h.vigente), None),
                "historico": hist,
                "origem": origem,
            }
        linhas.append(
            {
                "imposto": {"id": imp.id, "codigo": imp.codigo, "nome": imp.nome},
                "por_tipo": por_tipo,
            }
        )
    return {
        "tipos": [{"id": t.id, "codigo": t.codigo, "nome": t.nome} for t in tipos],
        "linhas": linhas,
    }


@router.post("/aliquotas/vigencias", status_code=status.HTTP_201_CREATED)
def nova_aliquota(dados: NovaAliquota, db: DB, usuario: Editar):
    if (
        db.get(Imposto, dados.imposto_id) is None
        or db.get(TipoImportacao, dados.tipo_importacao_id) is None
    ):
        raise ErroNegocio("Imposto ou tipo de importação não encontrado", status=404)
    nova = service.nova_vigencia_aliquota(
        db, dados.imposto_id, dados.tipo_importacao_id, dados.percentual, dados.vigencia_inicio,
        dados.justificativa, dados.origem, usuario.id,
    )  # fmt: skip
    db.commit()
    return {"id": nova.id}


@router.get("/componentes")
def listar_componentes(db: DB, _: Ler):
    hoje = date.today()
    saida = []
    for c in db.scalars(select(ComponenteCusto).order_by(ComponenteCusto.ordem)):
        f = service.formula_vigente(c, hoje)
        saida.append(
            {
                "id": c.id,
                "codigo": c.codigo,
                "nome": c.nome,
                "natureza": c.natureza,
                "compoe_provisao": c.compoe_provisao,
                "regra_competencia": c.regra_competencia,
                "ordem": c.ordem,
                "ativo": c.ativo,
                "formula": (
                    {
                        "id": f.id,
                        "versao": f.versao,
                        "expressao": f.expressao,
                        "vigencia_inicio": f.vigencia_inicio,
                    }  # fmt: skip
                    if f
                    else None
                ),
            }
        )
    return saida
