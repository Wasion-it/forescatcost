"""Modelo de dados do MVP (ver docs/03-modelo-de-dados.md)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

Dinheiro = Numeric(18, 2)
Taxa = Numeric(18, 6)
Percentual = Numeric(9, 6)


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


def _criado_em() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


# --------------------------------------------------------------------------- Segurança

usuario_perfil = Table(
    "usuario_perfil",
    Base.metadata,
    Column("usuario_id", ForeignKey("usuario.id", ondelete="CASCADE"), primary_key=True),
    Column("perfil_id", ForeignKey("perfil.id", ondelete="CASCADE"), primary_key=True),
)

perfil_permissao = Table(
    "perfil_permissao",
    Base.metadata,
    Column("perfil_id", ForeignKey("perfil.id", ondelete="CASCADE"), primary_key=True),
    Column("permissao_id", ForeignKey("permissao.id", ondelete="CASCADE"), primary_key=True),
)


class Permissao(Base):
    __tablename__ = "permissao"
    id: Mapped[uuid.UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(60), unique=True)
    descricao: Mapped[str] = mapped_column(String(200))


class Perfil(Base):
    __tablename__ = "perfil"
    id: Mapped[uuid.UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    permissoes: Mapped[list[Permissao]] = relationship(secondary=perfil_permissao, lazy="selectin")


class Usuario(Base):
    __tablename__ = "usuario"
    id: Mapped[uuid.UUID] = _uuid_pk()
    nome: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(160), unique=True)
    senha_hash: Mapped[str] = mapped_column(String(100))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    ultimo_acesso: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = _criado_em()
    perfis: Mapped[list[Perfil]] = relationship(secondary=usuario_perfil, lazy="selectin")

    @property
    def permissoes(self) -> set[str]:
        return {p.codigo for perfil in self.perfis for p in perfil.permissoes}


# --------------------------------------------------------------------------- Cadastros


class TipoImportacao(Base):
    __tablename__ = "tipo_importacao"
    id: Mapped[uuid.UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Moeda(Base):
    __tablename__ = "moeda"
    codigo: Mapped[str] = mapped_column(String(3), primary_key=True)
    nome: Mapped[str] = mapped_column(String(60))
    simbolo: Mapped[str] = mapped_column(String(5))


class Transportadora(Base):
    __tablename__ = "transportadora"
    id: Mapped[uuid.UUID] = _uuid_pk()
    nome: Mapped[str] = mapped_column(String(120))
    cnpj: Mapped[str | None] = mapped_column(String(18))
    tipo_servico: Mapped[str] = mapped_column(String(20))  # LOCAL
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = _criado_em()


class Despachante(Base):
    __tablename__ = "despachante"
    id: Mapped[uuid.UUID] = _uuid_pk()
    nome: Mapped[str] = mapped_column(String(120))
    cnpj: Mapped[str | None] = mapped_column(String(18))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = _criado_em()


class Terminal(Base):
    __tablename__ = "terminal"
    id: Mapped[uuid.UUID] = _uuid_pk()
    nome: Mapped[str] = mapped_column(String(120))
    modal: Mapped[str] = mapped_column(String(20))  # MARITIMO | AEREO
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_em: Mapped[datetime] = _criado_em()


# --------------------------------------------------------------------------- Parametrização


class Parametro(Base):
    __tablename__ = "parametro"
    id: Mapped[uuid.UUID] = _uuid_pk()
    chave: Mapped[str] = mapped_column(String(60), unique=True)
    descricao: Mapped[str] = mapped_column(String(200))
    # MONETARIO | PERCENTUAL | INTEIRO | BOOLEANO
    tipo_valor: Mapped[str] = mapped_column(String(20))
    escopo: Mapped[str] = mapped_column(String(30))
    # GLOBAL | TIPO_IMPORTACAO | TRANSP_LOCAL | DESPACHANTE | TERMINAL
    grupo: Mapped[str] = mapped_column(String(40))
    valores: Mapped[list[ParametroValor]] = relationship(
        back_populates="parametro", order_by="ParametroValor.vigencia_inicio.desc()"
    )


class ParametroValor(Base):
    __tablename__ = "parametro_valor"
    id: Mapped[uuid.UUID] = _uuid_pk()
    parametro_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("parametro.id"))
    escopo_ref_id: Mapped[uuid.UUID | None]
    valor: Mapped[Decimal] = mapped_column(Taxa)
    vigencia_inicio: Mapped[date] = mapped_column(Date)
    vigencia_fim: Mapped[date | None] = mapped_column(Date)
    justificativa: Mapped[str] = mapped_column(String(300))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = _criado_em()
    parametro: Mapped[Parametro] = relationship(back_populates="valores")


class Imposto(Base):
    __tablename__ = "imposto"
    id: Mapped[uuid.UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)


class Aliquota(Base):
    __tablename__ = "aliquota"
    id: Mapped[uuid.UUID] = _uuid_pk()
    imposto_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("imposto.id"))
    tipo_importacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tipo_importacao.id"))
    percentual: Mapped[Decimal] = mapped_column(Percentual)
    origem: Mapped[str] = mapped_column(String(20), default="MANUAL")  # MANUAL | TECWIN
    vigencia_inicio: Mapped[date] = mapped_column(Date)
    vigencia_fim: Mapped[date | None] = mapped_column(Date)
    justificativa: Mapped[str] = mapped_column(String(300))
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = _criado_em()
    imposto: Mapped[Imposto] = relationship(lazy="joined")


class ComponenteCusto(Base):
    __tablename__ = "componente_custo"
    id: Mapped[uuid.UUID] = _uuid_pk()
    codigo: Mapped[str] = mapped_column(String(30), unique=True)
    nome: Mapped[str] = mapped_column(String(80))
    natureza: Mapped[str] = mapped_column(String(20))  # BASE | IMPOSTO | TAXA | LOGISTICA | SERVICO
    compoe_provisao: Mapped[bool] = mapped_column(Boolean)
    regra_competencia: Mapped[str] = mapped_column(String(20))
    ordem: Mapped[int] = mapped_column(Integer)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    formulas: Mapped[list[Formula]] = relationship(
        back_populates="componente", order_by="Formula.versao.desc()", lazy="selectin"
    )


class Formula(Base):
    __tablename__ = "formula"
    __table_args__ = (UniqueConstraint("componente_id", "versao"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    componente_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("componente_custo.id"))
    versao: Mapped[int] = mapped_column(Integer)
    expressao: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))  # RASCUNHO | PUBLICADA | REVOGADA
    vigencia_inicio: Mapped[date] = mapped_column(Date)
    vigencia_fim: Mapped[date | None] = mapped_column(Date)
    criado_em: Mapped[datetime] = _criado_em()
    componente: Mapped[ComponenteCusto] = relationship(back_populates="formulas")


# --------------------------------------------------------------------------- Importação


class Importacao(Base):
    __tablename__ = "importacao"
    __table_args__ = (
        Index(
            "ux_importacao_ip",
            "numero_ip",
            unique=True,
            postgresql_where=text("numero_ip IS NOT NULL"),
        ),
        CheckConstraint(
            "status <> 'FECHADO' OR (valor_fatura IS NOT NULL AND valor_fatura > 0 "
            "AND numero_fatura IS NOT NULL AND numero_fatura <> '')",
            name="ck_importacao_fechamento",
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    numero: Mapped[int] = mapped_column(Integer, Identity(start=1), unique=True)
    numero_ip: Mapped[str | None] = mapped_column(String(30))
    data_ip: Mapped[date | None] = mapped_column(Date)
    data_prevista: Mapped[date | None] = mapped_column(Date)
    tipo_importacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tipo_importacao.id"))
    modal: Mapped[str] = mapped_column(String(20))
    valor_invoice: Mapped[Decimal] = mapped_column(Dinheiro)
    moeda_invoice: Mapped[str] = mapped_column(ForeignKey("moeda.codigo"))
    valor_frete: Mapped[Decimal] = mapped_column(Dinheiro)
    moeda_frete: Mapped[str] = mapped_column(ForeignKey("moeda.codigo"))
    qtd_itens: Mapped[int] = mapped_column(Integer)
    qtd_containers: Mapped[int] = mapped_column(Integer)
    taxa_usd: Mapped[Decimal | None] = mapped_column(Taxa)
    taxa_cny: Mapped[Decimal | None] = mapped_column(Taxa)
    valor_siscomex: Mapped[Decimal] = mapped_column(Dinheiro)
    valor_taxa_liberacao: Mapped[Decimal] = mapped_column(Dinheiro, default=Decimal(0))
    peso_bruto_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    peso_liquido_kg: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    valor_armazenagem_aerea: Mapped[Decimal] = mapped_column(Dinheiro, default=Decimal(0))
    transportadora_local_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("transportadora.id")
    )
    despachante_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("despachante.id"))
    terminal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("terminal.id"))
    # RASCUNHO | CALCULADO | FECHADO | CANCELADO
    status: Mapped[str] = mapped_column(String(20), default="RASCUNHO")
    calculo_desatualizado: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo_cancelamento: Mapped[str | None] = mapped_column(String(300))
    valor_fatura: Mapped[Decimal | None] = mapped_column(Dinheiro)
    numero_fatura: Mapped[str | None] = mapped_column(String(60))
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fechado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    observacoes: Mapped[str | None] = mapped_column(Text)
    versao: Mapped[int] = mapped_column(Integer, default=1)
    criado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    criado_em: Mapped[datetime] = _criado_em()
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    tipo_importacao: Mapped[TipoImportacao] = relationship(lazy="joined")
    transportadora_local: Mapped[Transportadora | None] = relationship(
        foreign_keys=[transportadora_local_id], lazy="joined"
    )
    despachante: Mapped[Despachante | None] = relationship(lazy="joined")
    terminal: Mapped[Terminal | None] = relationship(lazy="joined")
    fechador: Mapped[Usuario | None] = relationship(foreign_keys=[fechado_por], lazy="joined")

    __mapper_args__ = {"version_id_col": versao, "eager_defaults": True}

    @property
    def numero_processo(self) -> str:
        return f"IMP-{self.numero:05d}"

    @property
    def fechado_por_nome(self) -> str | None:
        return self.fechador.nome if self.fechador else None

    @property
    def data_referencia(self) -> date | None:
        return self.data_ip or self.data_prevista


# --------------------------------------------------------------------------- Cálculo


class Calculo(Base):
    __tablename__ = "calculo"
    __table_args__ = (
        UniqueConstraint("importacao_id", "numero_versao"),
        Index(
            "ux_calculo_vigente",
            "importacao_id",
            unique=True,
            postgresql_where=text("vigente"),
        ),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    importacao_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("importacao.id"))
    numero_versao: Mapped[int] = mapped_column(Integer)
    tipo: Mapped[str] = mapped_column(String(20), default="OFICIAL")
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)
    data_parametros: Mapped[date] = mapped_column(Date)
    data_referencia: Mapped[date] = mapped_column(Date)
    motivo: Mapped[str] = mapped_column(String(300))
    entradas_snapshot: Mapped[dict] = mapped_column(JSONB)
    parametros_snapshot: Mapped[dict] = mapped_column(JSONB)
    total_provisionado: Mapped[Decimal] = mapped_column(Dinheiro)
    hash_integridade: Mapped[str] = mapped_column(String(64))
    calculado_por: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("usuario.id"))
    calculado_em: Mapped[datetime] = _criado_em()

    itens: Mapped[list[CalculoItem]] = relationship(
        back_populates="calculo", order_by="CalculoItem.ordem", lazy="selectin"
    )
    usuario: Mapped[Usuario | None] = relationship(lazy="joined")


class CalculoItem(Base):
    __tablename__ = "calculo_item"
    __table_args__ = (Index("ix_calculo_item_competencia", "competencia", "componente_codigo"),)
    id: Mapped[uuid.UUID] = _uuid_pk()
    calculo_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("calculo.id", ondelete="CASCADE"))
    componente_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("componente_custo.id"))
    componente_codigo: Mapped[str] = mapped_column(String(30))
    componente_nome: Mapped[str] = mapped_column(String(80))
    natureza: Mapped[str] = mapped_column(String(20))
    formula_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("formula.id"))
    formula_versao: Mapped[int | None] = mapped_column(Integer)
    expressao: Mapped[str] = mapped_column(Text)
    valor: Mapped[Decimal] = mapped_column(Dinheiro)
    competencia: Mapped[date] = mapped_column(Date)
    compoe_provisao: Mapped[bool] = mapped_column(Boolean)
    ordem: Mapped[int] = mapped_column(Integer)
    memoria: Mapped[dict] = mapped_column(JSONB)
    calculo: Mapped[Calculo] = relationship(back_populates="itens")


# --------------------------------------------------------------------------- Auditoria


class Auditoria(Base):
    __tablename__ = "auditoria"
    __table_args__ = (
        Index("ix_auditoria_registro", "tabela", "registro_id"),
        Index("ix_auditoria_ocorrido", "ocorrido_em"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    tabela: Mapped[str] = mapped_column(String(60))
    registro_id: Mapped[str] = mapped_column(String(80))
    acao: Mapped[str] = mapped_column(String(10))
    dados_antes: Mapped[dict | None] = mapped_column(JSONB)
    dados_depois: Mapped[dict | None] = mapped_column(JSONB)
    campos_alterados: Mapped[list[str] | None] = mapped_column(JSONB)
    usuario_id: Mapped[uuid.UUID | None]
    correlation_id: Mapped[str | None] = mapped_column(String(64))
    ocorrido_em: Mapped[datetime] = _criado_em()
