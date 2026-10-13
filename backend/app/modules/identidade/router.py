"""Autenticação local (MVP) e gestão de usuários. SSO OIDC previsto no roadmap."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import Permissoes, exigir, usuario_atual
from app.core.erros import ErroNegocio
from app.core.security import criar_token, gerar_hash_senha, verificar_senha
from app.models import Perfil, Usuario

router = APIRouter(tags=["Identidade"])
DB = Annotated[Session, Depends(get_db)]
Gerir = Annotated[Usuario, Depends(exigir(Permissoes.USUARIO_GERIR))]

# Hash fixo para comparar quando o e-mail não existe (tempo de resposta uniforme)
_HASH_FALSO = gerar_hash_senha("senha-inexistente")

# Validação de formato simples: aceita domínios internos (ex.: empresa.local)
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=160, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]


class Login(BaseModel):
    email: Email
    senha: str = Field(min_length=1, max_length=128)


class PerfilSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    codigo: str
    nome: str


class UsuarioSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str
    email: str
    ativo: bool
    ultimo_acesso: datetime | None
    perfis: list[PerfilSaida]


class Sessao(BaseModel):
    token: str
    expira_em_segundos: int
    usuario: UsuarioSaida
    permissoes: list[str]


class UsuarioEntrada(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    email: Email
    senha: str | None = Field(default=None, min_length=10, max_length=128)
    ativo: bool = True
    perfis: list[str] = Field(min_length=1, description="Códigos dos perfis")


@router.post("/auth/login", response_model=Sessao)
def login(dados: Login, db: DB):
    usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == dados.email.lower()))
    senha_ok = verificar_senha(dados.senha, usuario.senha_hash if usuario else _HASH_FALSO)
    if usuario is None or not senha_ok or not usuario.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    usuario.ultimo_acesso = datetime.now(UTC)
    db.commit()
    token, expira = criar_token(usuario.id)
    return Sessao(
        token=token,
        expira_em_segundos=expira,
        usuario=UsuarioSaida.model_validate(usuario),
        permissoes=sorted(usuario.permissoes),
    )


@router.get("/auth/me")
def eu(usuario: Annotated[Usuario, Depends(usuario_atual)]):
    return {
        "usuario": UsuarioSaida.model_validate(usuario),
        "permissoes": sorted(usuario.permissoes),
    }


@router.get("/perfis", response_model=list[PerfilSaida])
def perfis(db: DB, _: Gerir):
    return db.scalars(select(Perfil).order_by(Perfil.nome)).all()


@router.get("/usuarios", response_model=list[UsuarioSaida])
def listar(db: DB, _: Gerir):
    return db.scalars(select(Usuario).order_by(Usuario.nome)).all()


def _perfis(db: Session, codigos: list[str]) -> list[Perfil]:
    encontrados = db.scalars(select(Perfil).where(Perfil.codigo.in_(codigos))).all()
    if len(encontrados) != len(set(codigos)):
        raise ErroNegocio("Perfil inválido")
    return list(encontrados)


@router.post("/usuarios", response_model=UsuarioSaida, status_code=status.HTTP_201_CREATED)
def criar(dados: UsuarioEntrada, db: DB, _: Gerir):
    if not dados.senha:
        raise ErroNegocio("Defina uma senha inicial com pelo menos 10 caracteres")
    if db.scalar(select(Usuario.id).where(func.lower(Usuario.email) == dados.email.lower())):
        raise ErroNegocio("Já existe usuário com este e-mail", status=409)
    usuario = Usuario(
        nome=dados.nome,
        email=dados.email.lower(),
        senha_hash=gerar_hash_senha(dados.senha),
        ativo=dados.ativo,
        perfis=_perfis(db, dados.perfis),
    )
    db.add(usuario)
    db.commit()
    return usuario


@router.put("/usuarios/{usuario_id}", response_model=UsuarioSaida)
def atualizar(usuario_id: UUID, dados: UsuarioEntrada, db: DB, admin: Gerir):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise ErroNegocio("Usuário não encontrado", status=404)
    if usuario.id == admin.id and (not dados.ativo or "ADMIN" not in dados.perfis):
        raise ErroNegocio("Você não pode remover o próprio acesso de administrador")
    duplicado = db.scalar(
        select(Usuario.id).where(
            func.lower(Usuario.email) == dados.email.lower(), Usuario.id != usuario_id
        )
    )
    if duplicado:
        raise ErroNegocio("Já existe usuário com este e-mail", status=409)
    usuario.nome = dados.nome
    usuario.email = dados.email.lower()
    usuario.ativo = dados.ativo
    usuario.perfis = _perfis(db, dados.perfis)
    if dados.senha:
        usuario.senha_hash = gerar_hash_senha(dados.senha)
    db.commit()
    return usuario
