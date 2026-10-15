from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Moeda = Literal["BRL", "USD", "CNY"]
Dinheiro = Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2)]
TaxaCambio = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=6)]
Peso = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=3)]


class ImportacaoEntrada(BaseModel):
    numero_ip: str | None = Field(default=None, max_length=30)
    data_ip: date | None = None
    data_prevista: date | None = None
    tipo_importacao_id: UUID
    modal: Literal["MARITIMO", "AEREO"]
    valor_invoice: Dinheiro
    moeda_invoice: Moeda
    valor_frete: Dinheiro
    moeda_frete: Moeda
    qtd_itens: int = Field(ge=0, le=100_000)
    qtd_containers: int = Field(ge=0, le=1_000)
    taxa_usd: TaxaCambio | None = None
    taxa_cny: TaxaCambio | None = None
    valor_siscomex: Dinheiro = Decimal(0)
    valor_taxa_liberacao: Dinheiro = Decimal(0)
    peso_bruto_kg: Peso = Decimal(0)
    peso_liquido_kg: Peso = Decimal(0)
    valor_armazenagem_aerea: Dinheiro = Decimal(0)
    transportadora_local_id: UUID | None = None
    despachante_id: UUID | None = None
    terminal_id: UUID | None = None
    observacoes: str | None = Field(default=None, max_length=2000)

    @field_validator("numero_ip", "observacoes", mode="before")
    @classmethod
    def _vazio_para_nulo(cls, v):
        if isinstance(v, str):
            v = v.strip()
            return v or None
        return v

    @model_validator(mode="after")
    def _regras(self) -> ImportacaoEntrada:
        erros: list[str] = []
        if self.data_ip is None and self.data_prevista is None:
            erros.append("Informe a data da IP ou a data prevista")
        moedas = {self.moeda_invoice, self.moeda_frete}
        if "USD" in moedas and self.taxa_usd is None:
            erros.append("Informe a taxa USD")
        if "CNY" in moedas and self.taxa_cny is None:
            erros.append("Informe a taxa CNY")
        if self.peso_liquido_kg > self.peso_bruto_kg:
            erros.append("O peso líquido não pode ser maior que o peso bruto")
        if erros:
            raise ValueError("; ".join(erros))
        return self


class ImportacaoAtualizacao(ImportacaoEntrada):
    versao: int


class FechamentoDespesa(BaseModel):
    versao: int
    valor_fatura: Annotated[Decimal, Field(gt=0, max_digits=16, decimal_places=2)]
    numero_fatura: str = Field(min_length=1, max_length=60)

    @field_validator("numero_fatura", mode="before")
    @classmethod
    def _apara_numero(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Informe o número da fatura")
        return v


class Cancelamento(BaseModel):
    motivo: str = Field(min_length=5, max_length=300)


class RefNome(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    nome: str


class TipoRef(RefNome):
    codigo: str


class CalculoItemSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    componente_codigo: str
    componente_nome: str
    natureza: str
    expressao: str
    formula_versao: int | None
    valor: Decimal
    competencia: date
    compoe_provisao: bool
    ordem: int
    memoria: dict


class CalculoSaida(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    numero_versao: int
    vigente: bool
    data_parametros: date
    data_referencia: date
    motivo: str
    total_provisionado: Decimal
    hash_integridade: str
    calculado_em: datetime
    calculado_por_nome: str | None = None
    itens: list[CalculoItemSaida]


class CalculoResumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    numero_versao: int
    vigente: bool
    motivo: str
    total_provisionado: Decimal
    calculado_em: datetime
    calculado_por_nome: str | None = None


class Diferenca(BaseModel):
    anterior: Decimal | None
    novo: Decimal
    diferenca: Decimal


class PreviaSaida(BaseModel):
    itens: list[CalculoItemSaida]
    total_provisionado: Decimal
    total_anterior: Decimal | None
    diferencas: dict[str, Diferenca]
    variaveis_base: dict[str, str]
    exige_motivo: bool


class RegistroCalculo(BaseModel):
    motivo: str | None = Field(default=None, max_length=300)


class ImportacaoResumo(BaseModel):
    id: UUID
    numero_processo: str
    numero_ip: str | None
    data_referencia: date | None
    data_ip: date | None
    tipo_importacao: TipoRef
    modal: str
    status: str
    calculo_desatualizado: bool
    total_provisionado: Decimal | None
    atualizado_em: datetime


class ImportacaoDetalhe(ImportacaoEntrada):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    numero_processo: str
    status: str
    calculo_desatualizado: bool
    motivo_cancelamento: str | None
    valor_fatura: Decimal | None = None
    numero_fatura: str | None = None
    fechado_em: datetime | None = None
    fechado_por_nome: str | None = None
    versao: int
    criado_em: datetime
    atualizado_em: datetime
    tipo_importacao: TipoRef
    transportadora_local: RefNome | None
    despachante: RefNome | None
    terminal: RefNome | None
    calculo_vigente: CalculoSaida | None = None

    # A saída não revalida as regras de entrada (dados já persistidos)
    @model_validator(mode="after")
    def _regras(self) -> ImportacaoDetalhe:
        return self


class Pagina(BaseModel):
    itens: list[ImportacaoResumo]
    total: int
    pagina: int
    tamanho: int
