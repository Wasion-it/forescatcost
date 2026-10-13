from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

_SQL_CONTEXTO = text(
    "SELECT set_config('app.usuario_id', :usuario_id, true), "
    "set_config('app.correlation_id', :correlation_id, true)"
)


def _aplicar_contexto(session: Session, connection) -> None:
    usuario_id = session.info.get("usuario_id")
    if usuario_id:
        connection.execute(
            _SQL_CONTEXTO,
            {
                "usuario_id": str(usuario_id),
                "correlation_id": session.info.get("correlation_id", ""),
            },
        )


@event.listens_for(Session, "after_begin")
def _contexto_auditoria(session: Session, _transaction, connection) -> None:
    """Propaga o usuário para a trigger de auditoria a cada nova transação."""
    _aplicar_contexto(session, connection)


def definir_usuario_sessao(db: Session, usuario_id: UUID, correlation_id: str = "") -> None:
    db.info["usuario_id"] = usuario_id
    db.info["correlation_id"] = correlation_id
    if db.in_transaction():
        _aplicar_contexto(db, db.connection())


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
