from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm.exc import StaleDataError

from app.calculo.engine import ErroCalculo


class ErroNegocio(Exception):
    """Violação de regra de negócio, devolvida como Problem Details (RFC 9457)."""

    def __init__(self, mensagem: str, status: int = 422, problemas: list[str] | None = None):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.status = status
        self.problemas = problemas or []


def _problema(status: int, titulo: str, detalhe: str, problemas: list[str] | None = None):
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "title": titulo,
            "status": status,
            "detail": detalhe,
            "problemas": problemas or [],
        },
    )


def registrar_handlers(app: FastAPI) -> None:
    @app.exception_handler(ErroNegocio)
    async def _negocio(_: Request, exc: ErroNegocio):
        return _problema(exc.status, "Regra de negócio", exc.mensagem, exc.problemas)

    @app.exception_handler(ErroCalculo)
    async def _calculo(_: Request, exc: ErroCalculo):
        return _problema(
            422,
            "Cálculo não concluído",
            "Corrija os itens abaixo e calcule de novo.",
            exc.problemas,
        )

    @app.exception_handler(StaleDataError)
    async def _concorrencia(_: Request, __: StaleDataError):
        return _problema(
            409,
            "Conflito de edição",
            "Outra pessoa alterou este registro. Recarregue a página para ver a versão atual.",
        )
