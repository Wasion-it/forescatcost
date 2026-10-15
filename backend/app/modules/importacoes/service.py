from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.erros import ErroNegocio
from app.models import (
    Calculo,
    Despachante,
    Importacao,
    Terminal,
    TipoImportacao,
    Transportadora,
    Usuario,
)
from app.modules.importacoes.schemas import (
    FechamentoDespesa,
    ImportacaoAtualizacao,
    ImportacaoEntrada,
)

CAMPOS_EDITAVEIS = [campo for campo in ImportacaoEntrada.model_fields if campo not in {"versao"}]


def _validar_referencias(db: Session, dados: ImportacaoEntrada) -> None:
    problemas = []
    checagens = [
        (TipoImportacao, dados.tipo_importacao_id, "Tipo de importação"),
        (Transportadora, dados.transportadora_local_id, "Transportadora local"),
        (Despachante, dados.despachante_id, "Despachante"),
        (Terminal, dados.terminal_id, "Terminal"),
    ]
    for modelo, ref_id, rotulo in checagens:
        if ref_id is None:
            continue
        obj = db.get(modelo, ref_id)
        if obj is None or not obj.ativo:
            problemas.append(f"{rotulo} não encontrado ou inativo")
    if problemas:
        raise ErroNegocio("Revise os vínculos do processo", problemas=problemas)


def _verificar_duplicidade(db: Session, dados: ImportacaoEntrada, ignorar_id: uuid.UUID | None):
    if not dados.numero_ip:
        return
    consulta = select(Importacao).where(Importacao.numero_ip == dados.numero_ip)
    if ignorar_id:
        consulta = consulta.where(Importacao.id != ignorar_id)
    existente = db.scalar(consulta)
    if existente:
        raise ErroNegocio(
            f"A IP {dados.numero_ip} já está no processo "
            f"{existente.numero_processo}",
            status=409,
        )


def criar(db: Session, dados: ImportacaoEntrada, usuario: Usuario) -> Importacao:
    _validar_referencias(db, dados)
    _verificar_duplicidade(db, dados, None)
    imp = Importacao(**dados.model_dump(), criado_por=usuario.id, status="RASCUNHO")
    db.add(imp)
    try:
        db.flush()
    except IntegrityError as exc:
        raise ErroNegocio("Número de IP já cadastrado", status=409) from exc
    return imp


def obter(db: Session, importacao_id: uuid.UUID) -> Importacao:
    imp = db.get(Importacao, importacao_id)
    if imp is None:
        raise ErroNegocio("Processo não encontrado", status=404)
    return imp


MSG_CONFLITO = "Outra pessoa alterou este processo. Recarregue a página para ver a versão atual."


def atualizar(db: Session, imp: Importacao, dados: ImportacaoAtualizacao) -> Importacao:
    if imp.status == "CANCELADO":
        raise ErroNegocio("Processo cancelado não pode ser editado")
    if imp.status == "FECHADO":
        raise ErroNegocio("Processo fechado não pode ser editado")
    if dados.versao != imp.versao:
        raise ErroNegocio(MSG_CONFLITO, status=409)
    _validar_referencias(db, dados)
    _verificar_duplicidade(db, dados, imp.id)
    novos = dados.model_dump(exclude={"versao"})
    mudou = any(getattr(imp, k) != v for k, v in novos.items())
    for campo, valor in novos.items():
        setattr(imp, campo, valor)
    if mudou and imp.status == "CALCULADO":
        imp.calculo_desatualizado = True
    db.flush()
    return imp


def cancelar(db: Session, imp: Importacao, motivo: str) -> Importacao:
    if imp.status == "CANCELADO":
        raise ErroNegocio("O processo já está cancelado")
    if imp.status == "FECHADO":
        raise ErroNegocio("Processo fechado não pode ser cancelado")
    imp.status = "CANCELADO"
    imp.motivo_cancelamento = motivo.strip()
    db.flush()
    return imp


def fechar(db: Session, imp: Importacao, dados: FechamentoDespesa, usuario: Usuario) -> Importacao:
    if dados.versao != imp.versao:
        raise ErroNegocio(MSG_CONFLITO, status=409)
    if imp.status == "FECHADO":
        raise ErroNegocio("A despesa já está fechada")
    if imp.status == "CANCELADO":
        raise ErroNegocio("Processo cancelado não pode ser fechado")
    if imp.status == "RASCUNHO":
        raise ErroNegocio("Calcule o processo antes de fechar a despesa")
    if imp.calculo_desatualizado:
        raise ErroNegocio("Recalcule o processo antes de fechar a despesa")
    imp.valor_fatura = dados.valor_fatura
    imp.numero_fatura = dados.numero_fatura
    imp.status = "FECHADO"
    imp.fechado_em = datetime.now(UTC)
    imp.fechador = usuario  # grava fechado_por e mantém fechado_por_nome atualizado
    db.flush()
    return imp


def consulta_lista(
    texto: str | None,
    tipo_codigo: str | None,
    status: str | None,
    de: date | None,
    ate: date | None,
) -> Select:
    data_ref = func.coalesce(Importacao.data_ip, Importacao.data_prevista)
    consulta = (
        select(Importacao, Calculo.total_provisionado)
        .join(TipoImportacao, TipoImportacao.id == Importacao.tipo_importacao_id)
        .outerjoin(Calculo, (Calculo.importacao_id == Importacao.id) & Calculo.vigente.is_(True))
    )
    if texto:
        termo = f"%{texto.strip()}%"
        filtro_numero = []
        digitos = "".join(ch for ch in texto if ch.isdigit())
        if texto.strip().upper().startswith("IMP-") and digitos:
            filtro_numero.append(Importacao.numero == int(digitos))
        consulta = consulta.where(
            or_(
                Importacao.numero_ip.ilike(termo),
                Importacao.observacoes.ilike(termo),
                *filtro_numero,
            )
        )
    if tipo_codigo:
        consulta = consulta.where(TipoImportacao.codigo == tipo_codigo)
    if status == "DESATUALIZADO":
        consulta = consulta.where(Importacao.calculo_desatualizado.is_(True))
    elif status:
        consulta = consulta.where(Importacao.status == status)
    if de:
        consulta = consulta.where(data_ref >= de)
    if ate:
        consulta = consulta.where(data_ref <= ate)
    return consulta.order_by(data_ref.desc().nulls_last(), Importacao.numero.desc())
