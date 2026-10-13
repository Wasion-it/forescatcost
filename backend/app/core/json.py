from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


def serializar(obj: Any) -> Any:
    """Converte Decimal em string (sem perda de precisão) para respostas sem response_model.

    O jsonable_encoder do FastAPI converte Decimal em float; aqui garantimos a ADR-006.
    """
    if isinstance(obj, Decimal):
        return format(obj, "f")
    if isinstance(obj, dict):
        return {str(k): serializar(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [serializar(v) for v in obj]
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, UUID):
        return str(obj)
    return obj
