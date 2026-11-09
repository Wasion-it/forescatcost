"""Fechamento da despesa item a item: cada item fecha com a própria fatura, conforme ela chega."""

from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal

_seq = count(500)


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


def _itens_despesa(imp):
    """Itens do cálculo vigente que compõem a despesa (cada um fecha com sua fatura)."""
    calculo = imp["calculo_vigente"] or {"itens": []}  # rascunho ainda não tem cálculo
    return [i for i in calculo["itens"] if i["compoe_provisao"]]


def _fechar_item(client, headers, imp, codigo, **campos):
    corpo = {
        "versao": imp["versao"],
        "numero_fatura": f"FT-{codigo}",
        "valor": "100.00",
        **campos,
    }
    corpo = {k: v for k, v in corpo.items() if v is not ...}
    return client.post(
        f"/api/v1/importacoes/{imp['id']}/despesas/{codigo}/fechar", json=corpo, headers=headers
    )


def _fechar_tudo(client, headers, imp, acrescimo="10.00"):
    """Fecha item a item (realizado = provisionado + acréscimo) e devolve o último detalhe."""
    for item in _itens_despesa(imp):
        valor = str(Decimal(item["valor"]) + Decimal(acrescimo))
        r = _fechar_item(client, headers, imp, item["componente_codigo"], valor=valor)
        assert r.status_code == 200, r.text
        imp = r.json()
    return imp


def test_fecha_um_item_por_vez_com_fatura_propria(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    itens = _itens_despesa(imp)
    assert len(itens) > 2
    primeiro, segundo = itens[0], itens[1]

    r = _fechar_item(
        client, pcm, imp, primeiro["componente_codigo"], numero_fatura="  FT-0001  ", valor="12.34"
    )
    assert r.status_code == 200, r.text
    parcial = r.json()
    # o processo continua calculado enquanto houver item pendente
    assert parcial["status"] == "CALCULADO"
    assert parcial["valor_fatura"] is None
    assert parcial["fechado_em"] is None
    assert parcial["versao"] > imp["versao"]
    [fechado] = parcial["despesas_fechadas"]
    assert fechado["componente_codigo"] == primeiro["componente_codigo"]
    assert fechado["numero_fatura"] == "FT-0001"  # espaços aparados
    assert Decimal(fechado["valor"]) == Decimal("12.34")
    assert Decimal(fechado["provisionado"]) == Decimal(primeiro["valor"])
    assert fechado["fechado_por_nome"] == "Analista PCM"
    assert fechado["fechado_em"]

    r = _fechar_item(client, pcm, parcial, segundo["componente_codigo"], numero_fatura="FT-0002")
    assert r.status_code == 200, r.text
    numeros = {d["componente_codigo"]: d["numero_fatura"] for d in r.json()["despesas_fechadas"]}
    assert numeros == {
        primeiro["componente_codigo"]: "FT-0001",
        segundo["componente_codigo"]: "FT-0002",
    }


def test_ultimo_item_fecha_o_processo(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    itens = _itens_despesa(imp)
    final = _fechar_tudo(client, pcm, imp)
    assert final["status"] == "FECHADO"
    esperado = sum((Decimal(i["valor"]) + Decimal("10.00") for i in itens), Decimal(0))
    assert Decimal(final["valor_fatura"]) == esperado
    assert final["numero_fatura"] is None  # o número fica em cada item
    assert final["fechado_por_nome"] == "Analista PCM"
    assert final["fechado_em"]
    assert final["calculo_vigente"]["numero_versao"] == 1

    detalhe = client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()
    fechadas = detalhe["despesas_fechadas"]
    assert [d["componente_codigo"] for d in fechadas] == [i["componente_codigo"] for i in itens]
    assert {d["numero_fatura"] for d in fechadas} == {f"FT-{i['componente_codigo']}" for i in itens}


def test_valor_do_item_pode_ser_zero(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    codigo = _itens_despesa(imp)[0]["componente_codigo"]
    r = _fechar_item(client, pcm, imp, codigo, valor="0.00")
    assert r.status_code == 200, r.text
    assert Decimal(r.json()["despesas_fechadas"][0]["valor"]) == 0


def test_total_zerado_nao_fecha_o_ultimo(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    for item in _itens_despesa(imp)[:-1]:
        r = _fechar_item(client, pcm, imp, item["componente_codigo"], valor="0.00")
        assert r.status_code == 200, r.text
        imp = r.json()
    ultimo = _itens_despesa(imp)[-1]["componente_codigo"]
    r = _fechar_item(client, pcm, imp, ultimo, valor="0.00")
    assert r.status_code == 422
    assert "maior que zero" in r.json()["detail"]
    r = _fechar_item(client, pcm, imp, ultimo, valor="0.01")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "FECHADO"


def test_fatura_invalida(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    codigo = _itens_despesa(imp)[0]["componente_codigo"]
    invalidos = [
        {"valor": ...},
        {"valor": "-10.00"},
        {"valor": "100.123"},
        {"numero_fatura": ...},
        {"numero_fatura": ""},
        {"numero_fatura": "   "},
        {"numero_fatura": "X" * 61},
    ]
    for campos in invalidos:
        r = _fechar_item(client, pcm, imp, codigo, **campos)
        assert r.status_code == 422, (campos, r.text)
    detalhe = client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()
    assert detalhe["status"] == "CALCULADO"
    assert detalhe["despesas_fechadas"] == []


def test_item_fora_da_despesa(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    r = _fechar_item(client, pcm, imp, "INEXISTENTE")
    assert r.status_code == 404
    assert "não faz parte da despesa" in r.json()["detail"]
    # itens da base de cálculo (CIF) não compõem a despesa
    base = [i for i in imp["calculo_vigente"]["itens"] if not i["compoe_provisao"]]
    if base:
        assert _fechar_item(client, pcm, imp, base[0]["componente_codigo"]).status_code == 404


def test_item_ja_fechado(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    item = _itens_despesa(imp)[0]
    parcial = _fechar_item(client, pcm, imp, item["componente_codigo"]).json()
    r = _fechar_item(client, pcm, parcial, item["componente_codigo"], numero_fatura="FT-OUTRA")
    assert r.status_code == 422
    assert f"{item['componente_nome']} já está fechada" in r.json()["detail"]


def test_rascunho_nao_fecha(client, pcm, payload):
    imp = _criar(client, pcm, payload)
    r = _fechar_item(client, pcm, imp, "II")
    assert r.status_code == 422
    assert "Calcule o processo" in r.json()["detail"]


def test_recalculo_pendente_nao_fecha(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    alterado = {**payload, "taxa_usd": "5.500000", "versao": imp["versao"]}
    r = client.put(f"/api/v1/importacoes/{imp['id']}", json=alterado, headers=pcm)
    assert r.status_code == 200, r.text
    assert r.json()["calculo_desatualizado"] is True
    r = _fechar_item(client, pcm, r.json(), _itens_despesa(imp)[0]["componente_codigo"])
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
    assert (
        _fechar_item(client, pcm, r.json(), _itens_despesa(imp)[0]["componente_codigo"]).status_code
        == 422
    )


def test_versao_desatualizada(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    itens = _itens_despesa(imp)
    r = _fechar_item(client, pcm, imp, itens[0]["componente_codigo"], versao=imp["versao"] + 50)
    assert r.status_code == 409
    assert "Recarregue" in r.json()["detail"]
    # fechar um item muda a versão: quem estava com a versão anterior precisa recarregar
    assert _fechar_item(client, pcm, imp, itens[0]["componente_codigo"]).status_code == 200
    assert _fechar_item(client, pcm, imp, itens[1]["componente_codigo"]).status_code == 409


def test_financeiro_nao_fecha(client, pcm, financeiro, payload):
    imp = _calculado(client, pcm, payload)
    codigo = _itens_despesa(imp)[0]["componente_codigo"]
    assert _fechar_item(client, financeiro, imp, codigo).status_code == 403
    assert (
        client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()["despesas_fechadas"]
        == []
    )


def _bloqueios(client, headers, imp, payload, palavra):
    alterado = {**payload, "observacoes": "tentativa", "versao": imp["versao"]}
    r = client.put(f"/api/v1/importacoes/{imp['id']}", json=alterado, headers=headers)
    assert r.status_code == 422
    assert palavra in r.json()["detail"]

    r = client.post(f"/api/v1/importacoes/{imp['id']}/calculos", json={}, headers=headers)
    assert r.status_code == 422
    assert palavra in r.json()["detail"]
    r = client.post(f"/api/v1/importacoes/{imp['id']}/calculos/previa", headers=headers)
    assert r.status_code == 422

    r = client.post(
        f"/api/v1/importacoes/{imp['id']}/cancelar",
        json={"motivo": "Tentativa de cancelar"},
        headers=headers,
    )
    assert r.status_code == 422
    assert palavra in r.json()["detail"]

    final = client.get(f"/api/v1/importacoes/{imp['id']}", headers=headers).json()
    assert final["observacoes"] is None
    assert final["calculo_vigente"]["numero_versao"] == 1
    return final


def test_despesa_parcial_nao_edita_nao_recalcula_nem_cancela(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    parcial = _fechar_item(client, pcm, imp, _itens_despesa(imp)[0]["componente_codigo"]).json()
    final = _bloqueios(client, pcm, parcial, payload, "despesa fechada")
    assert final["status"] == "CALCULADO"


def test_fechado_nao_edita_nao_recalcula_nem_cancela(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    fechado = _fechar_tudo(client, pcm, imp)
    r = _fechar_item(client, pcm, fechado, _itens_despesa(imp)[0]["componente_codigo"])
    assert r.status_code == 422
    assert "já está fechada" in r.json()["detail"]
    final = _bloqueios(client, pcm, fechado, payload, "fechado")
    assert final["status"] == "FECHADO"


def test_provisao_nao_muda_e_filtro_de_status(client, pcm, financeiro, payload):
    params = {"de": "2027-05-01", "ate": "2027-05-01"}
    imp = _calculado(client, pcm, payload)
    antes = client.get("/api/v1/provisoes/mensal", params=params, headers=financeiro).json()
    assert Decimal(antes["total"]) > 0

    _fechar_tudo(client, pcm, imp)
    depois = client.get("/api/v1/provisoes/mensal", params=params, headers=financeiro).json()
    assert depois["total"] == antes["total"]
    por_processo = client.get(
        "/api/v1/provisoes/por-processo", params=params, headers=financeiro
    ).json()
    assert imp["numero_processo"] in {ln["rotulo"] for ln in por_processo["linhas"]}

    r = client.get("/api/v1/importacoes", params={"status": "FECHADO", "tamanho": 200}, headers=pcm)
    assert r.status_code == 200
    ids = {i["id"] for i in r.json()["itens"]}
    assert imp["id"] in ids
    assert {i["status"] for i in r.json()["itens"]} == {"FECHADO"}


def test_auditoria_registra_fechamentos(client, pcm, admin, payload):
    imp = _calculado(client, pcm, payload)
    _fechar_tudo(client, pcm, imp)
    r = client.get(
        "/api/v1/auditoria",
        params={"tabela": "importacao", "registro_id": imp["id"]},
        headers=admin,
    ).json()
    ultimo = r["itens"][0]
    assert ultimo["acao"] == "UPDATE"
    assert ultimo["usuario_nome"] == "Analista PCM"
    assert {"status", "valor_fatura", "fechado_em", "fechado_por"} <= set(
        ultimo["campos_alterados"]
    )
    # cada item fechado fica registrado na própria tabela, com o usuário que fechou
    with SessionLocal() as db:
        linhas = db.execute(
            text(
                "SELECT dados_depois ->> 'numero_fatura', usuario_id IS NOT NULL FROM auditoria "
                "WHERE tabela = 'importacao_despesa' AND acao = 'INSERT' "
                "AND dados_depois ->> 'importacao_id' = :id"
            ),
            {"id": imp["id"]},
        ).all()
    assert {numero for numero, _ in linhas} == {
        f"FT-{i['componente_codigo']}" for i in _itens_despesa(imp)
    }
    assert all(com_usuario for _, com_usuario in linhas)


def test_constraints(client, pcm, payload):
    imp = _calculado(client, pcm, payload)
    sqls = [
        "UPDATE importacao SET status = 'FECHADO' WHERE id = :id",
        "UPDATE importacao SET status = 'FECHADO', valor_fatura = 0 WHERE id = :id",
    ]
    for sql in sqls:
        with SessionLocal() as db:
            with pytest.raises(IntegrityError, match="ck_importacao_fechamento"):
                db.execute(text(sql), {"id": imp["id"]})
                db.commit()
            db.rollback()

    item_id = imp["calculo_vigente"]["itens"][0]
    with SessionLocal() as db:
        calculo_item = db.execute(
            text(
                "SELECT ci.id FROM calculo_item ci JOIN calculo c ON c.id = ci.calculo_id "
                "WHERE c.importacao_id = :id AND ci.componente_codigo = :codigo"
            ),
            {"id": imp["id"], "codigo": item_id["componente_codigo"]},
        ).scalar_one()
        with pytest.raises(IntegrityError, match="ck_importacao_despesa_fatura"):
            db.execute(
                text(
                    "INSERT INTO importacao_despesa (id, importacao_id, calculo_item_id, valor, "
                    "numero_fatura) VALUES (gen_random_uuid(), :id, :item, 1, '')"
                ),
                {"id": imp["id"], "item": calculo_item},
            )
            db.commit()
        db.rollback()
    assert client.get(f"/api/v1/importacoes/{imp['id']}", headers=pcm).json()["status"] == (
        "CALCULADO"
    )
