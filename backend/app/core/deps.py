from collections.abc import Callable
from uuid import UUID, uuid4

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import definir_usuario_sessao, get_db
from app.core.security import decodificar_token
from app.models import Usuario

_bearer = HTTPBearer(auto_error=False)


def usuario_atual(
    request: Request,
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    nao_autenticado = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        "Sessão inválida ou expirada. Entre novamente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credenciais is None:
        raise nao_autenticado
    try:
        usuario_id: UUID = decodificar_token(credenciais.credentials)
    except (jwt.PyJWTError, KeyError, ValueError):
        raise nao_autenticado from None
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise nao_autenticado
    correlation_id = request.headers.get("x-correlation-id") or uuid4().hex
    definir_usuario_sessao(db, usuario.id, correlation_id[:64])
    return usuario


def exigir(permissao: str) -> Callable[[Usuario], Usuario]:
    """Dependência que exige uma permissão granular (ex.: ``importacao:editar``)."""

    def _verificar(usuario: Usuario = Depends(usuario_atual)) -> Usuario:
        if permissao not in usuario.permissoes:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"Seu perfil não tem a permissão {permissao}."
            )
        return usuario

    return _verificar


class Permissoes:
    IMPORTACAO_LER = "importacao:ler"
    IMPORTACAO_EDITAR = "importacao:editar"
    CALCULO_EXECUTAR = "calculo:executar"
    PARAMETRO_LER = "parametro:ler"
    PARAMETRO_EDITAR = "parametro:editar"
    CADASTRO_EDITAR = "cadastro:editar"
    PROVISAO_LER = "provisao:ler"
    AUDITORIA_LER = "auditoria:ler"
    USUARIO_GERIR = "usuario:gerir"
