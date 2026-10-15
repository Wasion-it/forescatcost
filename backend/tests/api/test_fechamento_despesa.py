"""Fechamento da despesa por processo: regras, bloqueios, provisão, auditoria e constraint."""

from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal

_seq = count(500)
FECHAMENTO = {"valor_fatura": "61234.56", "numero_fatura": "FT-2026/0412"}


@pytest.fixture
def payload(refs):
    n = next(_seq)
    return {
        "numero_ip": f"IP-26-{n:04d}",
        "data_ip": "2027-05-10",  # mês isolado dos demais testes
        "tipo_importacao_id": refs["tipos"]["USO_CONSUMO"],
        "modal": "MARITIMO",
        "valor_invoice": "10000.00",
        "moeda_invoice": "USD",
        "valor_frete": "2000.00",
        "moeda_frete": "USD",
        "qtd_itens": 10,
        "qtd_containers": 2,
        "taxa_usd": "5.000000",
        "valor_siscomex": "154.23",
        "valor_taxa_liberacao": "350.00",
        "peso_bruto_kg": "12000",
        "peso_liquido_kg": "11000",
        "transportadora_local_id": refs["transp"]["Rodo Norte Logística"],
        "despachante_id": refs["despachante"],
        "terminal_id": refs["term"]["Chibatão"],
    }


def _criar(client, headers, payload):
    r = client.post("/api/v1/importacoes", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _calculado(client, headers, payload):
    imp = _criar(client, headers, payload)
    r = client.post(f"/api/v1/importacoes/{imp['id']}/calculos", json={}, headers=headers)
    assert r.status_code == 201, r.text
    return client.get(f"/api/v1/importacoes/{imp['id']}", headers=headers).json()


def _fechar(client, headers, imp, **campos):
    corpo = {"versao": imp["versao"], **FECHAMENTO, **campos}
    corpo = {k: v for k, v in corpo.items() if v is not ...}
    return client.post(f"/api/v1/importacoes/{imp['id']}/fechar", json=corpo, headers=headers)


def test_fechamento_valido(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    r = _fechar(client, pcm, imp, numero_fatura="  FT-2026/0412  ")
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["status"] == "FECHADO"
    assert corpo["valor_fatura"] == "61234.56"
    assert corpo["numero_fatura"] == "FT-2026/0412"  # espaços aparados
    assert corpo["fechado_por_nome"] == "Analista PCM"
    assert corpo["fechado_em"]
    assert corpo["calculo_desatualizado"] is False
    assert corpo["calculo_vigente"]["numero_versao"] == 1

    detalhe = client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()
    assert detalhe["status"] == "FECHADO"
    assert detalhe["numero_fatura"] == "FT-2026/0412"


def test_fatura_invalida(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    invalidos = [
        {"valor_fatura": ...},
        {"valor_fatura": "0"},
        {"valor_fatura": "0.00"},
        {"valor_fatura": "-10.00"},
        {"valor_fatura": "100.123"},
        {"numero_fatura": ...},
        {"numero_fatura": ""},
        {"numero_fatura": "   "},
        {"numero_fatura": "X" * 61},
    ]
    for campos in invalidos:
        r = _fechar(client, pcm, imp, **campos)
        assert r.status_code == 422, (campos, r.text)
    detalhe = client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()
    assert detalhe["status"] == "CALCULADO"
    assert detalhe["valor_fatura"] is None


def test_rascunho_nao_fecha(client, pcm, payload):
    imp = _criar(client, pcm, payload)
    r = _fechar(client, pcm, imp)
    assert r.status_code == 422
    assert "Calcule o processo" in r.json()["detail"]


def test_recalculo_pendente_nao_fecha(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    alterado = {**payload, "taxa_usd": "5.500000", "versao": imp["versao"]}
    r = client.put(f"/api/v1/importacoes/{imp['id']}", json=alterado, headers=pcm)
    assert r.status_code == 200, r.text
    assert r.json()["calculo_desatualizado"] is True
    r = _fechar(client, pcm, r.json())
    assert r.status_code == 422
    assert "Recalcule o processo" in r.json()["detail"]


def test_cancelado_nao_fecha(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    r = client.post(
        f"/api/v1/importacoes/{imp['id']}/cancelar",
        json={"motivo": "Pedido cancelado"},
        headers=pcm,
    )
    assert r.status_code == 200, r.text
    assert _fechar(client, pcm, r.json()).status_code == 422


def test_versao_desatualizada(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    r = _fechar(client, pcm, imp, versao=imp["versao"] + 50)
    assert r.status_code == 409
    assert "Recarregue" in r.json()["detail"]


def test_financeiro_nao_fecha(client, pcm, financeiro, payload):
    imp = _calculado(client, pcm, payload)
    assert _fechar(client, financeiro, imp).status_code == 403
    assert client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()["status"] == (
        "CALCULADO"
    )


def test_fechado_nao_edita_nao_recalcula_nem_cancela(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    fechado = _fechar(client, pcm, imp).json()

    r = _fechar(client, pcm, fechado)
    assert r.status_code == 422
    assert "já está fechada" in r.json()["detail"]

    alterado = {**payload, "observacoes": "tentativa", "versao": fechado["versao"]}
    r = client.put(f"/api/v1/importacoes/{imp['id']}", json=alterado, headers=pcm)
    assert r.status_code == 422
    assert "fechado" in r.json()["detail"]

    r = client.post(f"/api/v1/importacoes/{imp['id']}/calculos", json={}, headers=pcm)
    assert r.status_code == 422
    assert "fechado" in r.json()["detail"]
    r = client.post(f"/api/v1/importacoes/{imp['id']}/calculos/previa", headers=pcm)
    assert r.status_code == 422

    r = client.post(
        f"/api/v1/importacoes/{imp['id']}/cancelar", json={"motivo": "Tentativa de cancelar"},
        headers=pcm,
    )
    assert r.status_code == 422
    assert "fechado" in r.json()["detail"]

    final = client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()
    assert final["status"] == "FECHADO"
    assert final["observacoes"] is None
    assert final["calculo_vigente"]["numero_versao"] == 1


def test_provisao_nao_muda_e_filtro_de_status(client, pcm, financeiro, payload):
    params = {"de": "2027-05-01", "ate": "2027-05-01"}
    imp = _calculado(client, pcm, payload)
    antes = client.get("/api/v1/provisoes/mensal", params=params, headers=financeiro).json()
    assert Decimal(antes["total"]) > 0

    assert _fechar(client, pcm, imp).status_code == 200
    depois = client.get("/api/v1/provisoes/mensal", params=params, headers=financeiro).json()
    assert depois["total"] == antes["total"]
    por_processo = client.get(
        "/api/v1/provisoes/por-processo", params=params, headers=financeiro
    ).json()
    assert imp["numero_processo"] in {ln["rotulo"] for ln in por_processo["linhas"]}

    r = client.get(
        "/api/v1/importacoes", params={"status": "FECHADO", "tamanho": 200}, headers=pcm
    )
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["itens"]}
    assert imp["id"] in ids
    assert {i["status"] for i in r.json()["itens"]} == {"FECHADO"}


def test_auditoria_registra_fechamento(client, pcm, admin, payload):
    imp = _calculado(client, pcm, payload)
    assert _fechar(client, pcm, imp).status_code == 200
    r = client.get(
        "/api/v1/auditoria",
        params={"tabela": "importacao", "registro_id": imp["id"]},
        headers=admin,
    ).json()
    ultimo = r["itens"][0]
    assert ultimo["acao"] == "UPDATE"
    assert ultimo["usuario_nome"] == "Analista PCM"
    assert {
        "status",
        "valor_fatura",
        "numero_fatura",
        "fechado_em",
        "fechado_por",
    } <= set(ultimo["campos_alterados"])


def test_constraint_recusa_fechado_sem_fatura(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    sqls = [
        "UPDATE importacao SET status = 'FECHADO' WHERE id = :id",
        "UPDATE importacao SET status = 'FECHADO', valor_fatura = 0, numero_fatura = 'FT-1' "
        "WHERE id = :id",
        "UPDATE importacao SET status = 'FECHADO', valor_fatura = 10, numero_fatura = '' "
        "WHERE id = :id",
        "UPDATE importacao SET status = 'FECHADO', valor_fatura = 10 WHERE id = :id",
    ]
    for sql in sqls:
        with SessionLocal() as db:
            with pytest.raises(IntegrityError, match="ck_importacao_fechamento"):
                db.execute(text(sql), {"id": imp["id"]})
                db.commit()
            db.rollback()
    assert client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()["status"] == (
        "CALCULADO"
    )
