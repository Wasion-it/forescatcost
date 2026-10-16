from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

_SEGREDO_DEV = "dev-inseguro-troque-em-producao-0123456789abcdef"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ambiente: str = Field(default="dev", description="dev | hml | prd")
    database_url: str = "postgresql+psycopg://forecast:forecast_dev@localhost:5433/forecast"
    jwt_segredo: str = _SEGREDO_DEV
    jwt_algoritmo: str = "HS256"
    jwt_expiracao_minutos: int = 480
    cors_origens: list[str] = ["http://localhost:5173"]

    # Metadados injetados pelo pipeline para rastreabilidade do deploy.
    app_version: str = "0.1.0-dev"
    app_commit: str = "unknown"
    app_environment: str = "dev"

    def validar_producao(self) -> None:
        if not self.jwt_segredo:
            self.jwt_segredo = _SEGREDO_DEV
        if self.ambiente != "dev" and self.jwt_segredo == _SEGREDO_DEV:
            raise RuntimeError("Defina JWT_SEGREDO fora do ambiente de desenvolvimento")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validar_producao()
    return settings
