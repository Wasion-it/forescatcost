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

    # --- LDAP / Active Directory (login de usuários comuns; o admin local continua por senha)
    ldap_enabled: bool = False
    ldap_server_uri: str = ""  # ex.: ldaps://ad.empresa.local:636 ou ldap://ad.empresa.local:389
    ldap_use_ssl: bool = False  # LDAPS (porta 636)
    ldap_start_tls: bool = False  # usar com ldap:// (porta 389) para cifrar a conexão
    ldap_validate_certificates: bool = True  # false só em testes
    ldap_ca_arquivo: str = ""  # CA interna (PEM) para validar o certificado do servidor
    ldap_timeout_seconds: int = 5
    ldap_user_base_dn: str = ""  # ex.: DC=empresa,DC=local
    # Conta de serviço para localizar o usuário (usada quando LDAP_USER_DN_TEMPLATE está vazio)
    ldap_bind_dn: str = ""
    ldap_bind_password: str = ""
    # Se preenchido, faz o bind direto com o usuário, sem busca prévia.
    # Ex.: {username}@empresa.local ou EMPRESA\{username}
    ldap_user_dn_template: str = ""
    ldap_user_filter: str = "(sAMAccountName={username})"
    ldap_attr_login: str = "sAMAccountName"
    ldap_attr_nome: str = "displayName"
    ldap_attr_email: str = "mail"
    # Perfil dado ao usuário LDAP na primeira entrada (o admin ajusta depois em Usuários)
    ldap_perfil_padrao: str = "FINANCEIRO"

    def validar_producao(self) -> None:
        if not self.jwt_segredo:
            self.jwt_segredo = _SEGREDO_DEV
        if self.ambiente != "dev" and self.jwt_segredo == _SEGREDO_DEV:
            raise RuntimeError("Defina JWT_SEGREDO fora do ambiente de desenvolvimento")
        if self.ldap_enabled:
            if not self.ldap_server_uri or not self.ldap_user_base_dn:
                raise RuntimeError("LDAP_ENABLED exige LDAP_SERVER_URI e LDAP_USER_BASE_DN")
            if not self.ldap_bind_dn and not self.ldap_user_dn_template:
                raise RuntimeError(
                    "Informe LDAP_BIND_DN (conta de serviço) ou LDAP_USER_DN_TEMPLATE"
                )
            if "{username}" not in self.ldap_user_filter:
                raise RuntimeError("LDAP_USER_FILTER precisa conter {username}")
            if self.ambiente != "dev":
                if not (self.ldap_use_ssl or self.ldap_start_tls):
                    raise RuntimeError("LDAP sem TLS: use LDAP_USE_SSL ou LDAP_START_TLS")
                if not self.ldap_validate_certificates:
                    raise RuntimeError("LDAP_VALIDATE_CERTIFICATES=false só é aceito em dev")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validar_producao()
    return settings
