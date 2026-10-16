from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.erros import registrar_handlers
from app.modules.auditoria.router import router as auditoria
from app.modules.cadastros.router import router as cadastros
from app.modules.identidade.router import router as identidade
from app.modules.importacoes.router import router as importacoes
from app.modules.parametros.router import router as parametros
from app.modules.provisoes.router import router as provisoes

settings = get_settings()

app = FastAPI(
    title="Forecast de Importação",
    version=settings.app_version,
    description="Previsão de custos e impostos de importação (PCM → Financeiro).",
    docs_url="/api/docs" if settings.ambiente != "prd" else None,
    openapi_url="/api/openapi.json" if settings.ambiente != "prd" else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origens,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["Authorization", "Content-Type", "X-Correlation-Id"],
)
registrar_handlers(app)

api = APIRouter(prefix="/api/v1")
for r in (identidade, cadastros, parametros, importacoes, provisoes, auditoria):
    api.include_router(r)
app.include_router(api)


def _health_payload() -> dict[str, str]:
    return {
        "status": "ok",
        "version": settings.app_version,
        "commit": settings.app_commit,
        "environment": settings.app_environment,
    }


@app.get("/health", include_in_schema=False)
def health():
    return _health_payload()


@app.get("/api/v1/health", include_in_schema=False)
def api_health():
    return _health_payload()
