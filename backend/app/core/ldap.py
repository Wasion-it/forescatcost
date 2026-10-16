"""Autenticação por LDAP / Active Directory.

Fluxo: localiza o usuário (conta de serviço, ou bind direto por LDAP_USER_DN_TEMPLATE), confirma a
senha fazendo bind com as credenciais dele e devolve nome e e-mail. Nenhuma senha é armazenada.
"""

import logging
import re
import ssl
from dataclasses import dataclass

from ldap3 import NONE, SIMPLE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError, LDAPException, LDAPInvalidCredentialsResult
from ldap3.utils.conv import escape_filter_chars

from app.core.config import get_settings

log = logging.getLogger(__name__)

# sAMAccountName não admite  " / \ [ ] : ; | = , + * ? < >  nem espaços de borda. Restringir
# evita injeção de DN/filtro quando o login entra no template de bind.
_LOGIN_VALIDO = re.compile(r"^[\w.\-]{1,64}$")


class LdapIndisponivel(Exception):
    """Servidor LDAP inacessível ou mal configurado (diferente de credencial inválida)."""


@dataclass(frozen=True)
class IdentidadeLdap:
    login: str
    nome: str
    email: str | None


def _servidor() -> Server:
    s = get_settings()
    tls = Tls(
        validate=ssl.CERT_REQUIRED if s.ldap_validate_certificates else ssl.CERT_NONE,
        ca_certs_file=s.ldap_ca_arquivo or None,
        version=ssl.PROTOCOL_TLS_CLIENT,
    )
    return Server(
        s.ldap_server_uri,
        use_ssl=s.ldap_use_ssl or s.ldap_server_uri.lower().startswith("ldaps://"),
        tls=tls,
        connect_timeout=s.ldap_timeout_seconds,
        get_info=NONE,
    )


def _conectar(usuario: str, senha: str) -> Connection | None:
    """Abre e autentica a conexão. Devolve None se a credencial for recusada."""
    s = get_settings()
    conn = Connection(
        _servidor(),
        user=usuario,
        password=senha,
        authentication=SIMPLE,
        receive_timeout=s.ldap_timeout_seconds,
        raise_exceptions=True,
    )
    try:
        if s.ldap_start_tls:
            conn.open()
            conn.start_tls()
        conn.bind()
    except (LDAPBindError, LDAPInvalidCredentialsResult):
        return None
    return conn


def _valor(entrada, atributo: str) -> str | None:
    """Primeiro valor do atributo (busca sem diferenciar maiúsculas), ou None."""
    if not atributo:
        return None
    for nome, valores in entrada.entry_attributes_as_dict.items():
        if nome.lower() == atributo.lower():
            primeiro = valores[0] if isinstance(valores, list) and valores else valores
            texto = str(primeiro).strip() if primeiro not in (None, [], "") else ""
            return texto or None
    return None


def autenticar(login: str, senha: str) -> IdentidadeLdap | None:
    """Valida login (sAMAccountName) e senha no diretório.

    Devolve a identidade quando válidos e None quando o usuário não existe ou a senha está
    errada. Levanta LdapIndisponivel se o diretório não puder ser consultado.
    """
    s = get_settings()
    # Senha vazia viraria bind anônimo (aceito por muitos servidores): nunca enviar.
    if not senha or not _LOGIN_VALIDO.fullmatch(login or ""):
        return None

    atributos = [a for a in (s.ldap_attr_login, s.ldap_attr_nome, s.ldap_attr_email) if a]
    filtro = s.ldap_user_filter.replace("{username}", escape_filter_chars(login))
    conexoes: list[Connection] = []
    try:
        if s.ldap_user_dn_template:
            # Bind direto: o próprio usuário consulta os seus atributos
            usuario = _conectar(s.ldap_user_dn_template.replace("{username}", login), senha)
            if usuario is None:
                return None
            conexoes.append(usuario)
            usuario.search(s.ldap_user_base_dn, filtro, attributes=atributos, size_limit=2)
            if len(usuario.entries) != 1:
                return None
            entrada = usuario.entries[0]
        else:
            servico = _conectar(s.ldap_bind_dn, s.ldap_bind_password)
            if servico is None:
                raise LdapIndisponivel("Conta de serviço LDAP recusada")
            conexoes.append(servico)
            servico.search(s.ldap_user_base_dn, filtro, attributes=atributos, size_limit=2)
            if len(servico.entries) != 1:
                return None
            entrada = servico.entries[0]
            usuario = _conectar(entrada.entry_dn, senha)
            if usuario is None:
                return None
            conexoes.append(usuario)
    except LDAPException as exc:
        log.error("Falha ao consultar o LDAP: %s", exc)
        raise LdapIndisponivel(str(exc)) from exc
    finally:
        for c in conexoes:
            c.unbind()

    return IdentidadeLdap(
        login=(_valor(entrada, s.ldap_attr_login) or login).lower(),
        nome=_valor(entrada, s.ldap_attr_nome) or login,
        email=(_valor(entrada, s.ldap_attr_email) or "").lower() or None,
    )
