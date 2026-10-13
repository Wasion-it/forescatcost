from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
import jwt

from app.core.config import get_settings


def gerar_hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("ascii")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("ascii"))
    except ValueError:
        return False


def criar_token(usuario_id: UUID) -> tuple[str, int]:
    s = get_settings()
    expira_em = timedelta(minutes=s.jwt_expiracao_minutos)
    agora = datetime.now(UTC)
    payload = {"sub": str(usuario_id), "iat": agora, "exp": agora + expira_em, "aud": "forecast"}
    return jwt.encode(payload, s.jwt_segredo, algorithm=s.jwt_algoritmo), int(
        expira_em.total_seconds()
    )


def decodificar_token(token: str) -> UUID:
    s = get_settings()
    payload = jwt.decode(token, s.jwt_segredo, algorithms=[s.jwt_algoritmo], audience="forecast")
    return UUID(payload["sub"])
