"""Cadastros de apoio: tipos, moedas, transportadoras, despachantes e terminais."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import Permissoes, exigir, usuario_atual
from app.core.erros import ErroNegocio
from app.models import Despachante, Moeda, Terminal, TipoImportacao, Transportadora, Usuario

router = APIRouter(tags=["Cadastros"])
DB = Annotated[Session, Depends(get_db)]
Autenticado = Annotated[Usuario, Depends(usuario_atual)]
Editar = Annotated[Usuario, Depends(exigir(Permissoes.CADASTRO_EDITAR))]


class TipoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    codigo: str
    nome: str
    ativo: bool


class MoedaSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    codigo: str
    nome: str
    simbolo: str


class _Base(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    cnpj: str | None = Field(default=None, pattern=r"^\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}$")
    ativo: bool = True


class TransportadoraEntrada(_Base):
    tipo_servico: Literal["LOCAL", "SECUNDARIO", "AMBOS"]


class DespachanteEntrada(_Base):
    pass


class TerminalEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    modal: Literal["MARITIMO", "AEREO"]
    ativo: bool = True


class TransportadoraSaida(TransportadoraEntrada):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class DespachanteSaida(DespachanteEntrada):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class TerminalSaida(TerminalEntrada):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


@router.get("/tipos-importacao", response_model=list[TipoSaida])
def tipos(db: DB, _: Autenticado):
    return db.scalars(select(TipoImportacao).order_by(TipoImportacao.nome)).all()


@router.get("/moedas", response_model=list[MoedaSaida])
def moedas(db: DB, _: Autenticado):
    return db.scalars(select(Moeda).order_by(Moeda.codigo)).all()


def _registrar_crud(caminho: str, modelo, entrada, saida, rotulo: str) -> None:
    @router.get(f"/{caminho}", response_model=list[saida], name=f"listar_{caminho}")
    def listar(db: DB, _: Autenticado, incluir_inativos: bool = False):
        consulta = select(modelo).order_by(modelo.nome)
        if not incluir_inativos:
            consulta = consulta.where(modelo.ativo.is_(True))
        return db.scalars(consulta).all()

    @router.post(
        f"/{caminho}", response_model=saida, status_code=status.HTTP_201_CREATED,
        name=f"criar_{caminho}",
    )  # fmt: skip
    def criar(dados: entrada, db: DB, _: Editar):  # type: ignore[valid-type]
        obj = modelo(**dados.model_dump())
        db.add(obj)
        db.commit()
        return obj

    @router.put(f"/{caminho}/{{obj_id}}", response_model=saida, name=f"atualizar_{caminho}")
    def atualizar(obj_id: UUID, dados: entrada, db: DB, _: Editar):  # type: ignore[valid-type]
        obj = db.get(modelo, obj_id)
        if obj is None:
            raise ErroNegocio(f"{rotulo} não encontrado", status=404)
        for campo, valor in dados.model_dump().items():
            setattr(obj, campo, valor)
        db.commit()
        return obj


_registrar_crud(
    "transportadoras", Transportadora, TransportadoraEntrada, TransportadoraSaida, "Transportadora"
)
_registrar_crud("despachantes", Despachante, DespachanteEntrada, DespachanteSaida, "Despachante")
_registrar_crud("terminais", Terminal, TerminalEntrada, TerminalSaida, "Terminal")
