"""login via LDAP: origem do usuário e login do diretório

Revision ID: f2a6c8d4e9b1
Revises: e7f1a9c3b5d2
Create Date: 2026-10-16 11:00:00

Esquema:
- usuario.origem ('LOCAL' | 'LDAP'), padrão 'LOCAL' (usuários existentes continuam locais);
- usuario.login_ldap (sAMAccountName), único; nulo para usuários locais;
- usuario.senha_hash passa a aceitar nulo (usuários LDAP não têm senha local).
Downgrade: remove as colunas e volta senha_hash para NOT NULL. Usuários LDAP não têm senha e
ficam com um hash inválido, portanto sem acesso local.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f2a6c8d4e9b1"
down_revision: str | Sequence[str] | None = "e7f1a9c3b5d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "usuario",
        sa.Column("origem", sa.String(length=10), server_default="LOCAL", nullable=False),
    )
    op.add_column("usuario", sa.Column("login_ldap", sa.String(length=120), nullable=True))
    op.create_unique_constraint("uq_usuario_login_ldap", "usuario", ["login_ldap"])
    op.create_check_constraint("ck_usuario_origem", "usuario", "origem IN ('LOCAL', 'LDAP')")
    op.alter_column("usuario", "senha_hash", existing_type=sa.String(length=100), nullable=True)
    # Usuário local precisa de senha; usuário LDAP precisa de login do diretório
    op.create_check_constraint(
        "ck_usuario_credencial",
        "usuario",
        "(origem = 'LOCAL' AND senha_hash IS NOT NULL) "
        "OR (origem = 'LDAP' AND login_ldap IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_usuario_credencial", "usuario", type_="check")
    op.execute("UPDATE usuario SET senha_hash = '!' WHERE senha_hash IS NULL")
    op.alter_column("usuario", "senha_hash", existing_type=sa.String(length=100), nullable=False)
    op.drop_constraint("ck_usuario_origem", "usuario", type_="check")
    op.drop_constraint("uq_usuario_login_ldap", "usuario", type_="unique")
    op.drop_column("usuario", "login_ldap")
    op.drop_column("usuario", "origem")
