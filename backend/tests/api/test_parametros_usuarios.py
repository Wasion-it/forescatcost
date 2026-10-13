from datetime import date, timedelta


def _param(client, headers, chave):
    return next(
        p for p in client.get("/api/v1/parametros", headers=headers).json() if p["chave"] == chave
    )


def test_nova_vigencia_encerra_anterior(client, pcm):
    p = _param(client, pcm, "taxa_liberacao")
    inicio = date.today() + timedelta(days=30)
    r = client.post(
        f"/api/v1/parametros/{p['id']}/vigencias",
        json={
            "valor": "400",
            "vigencia_inicio": inicio.isoformat(),
            "justificativa": "Reajuste do agente",
        },
        headers=pcm,
    )
    assert r.status_code == 201, r.text
    p = _param(client, pcm, "taxa_liberacao")
    hist = p["valores"][0]["historico"]
    assert hist[0]["valor"] == "400.000000" and hist[0]["vigencia_fim"] is None
    assert hist[1]["vigencia_fim"] == (inicio - timedelta(days=1)).isoformat()
    # o valor vigente hoje continua o anterior
    assert p["valores"][0]["vigente"]["valor"] == "350.000000"


def test_vigencia_retroativa_rejeitada(client, pcm):
    p = _param(client, pcm, "tcif_valor_item")
    r = client.post(
        f"/api/v1/parametros/{p['id']}/vigencias",
        json={"valor": "50", "vigencia_inicio": "2025-06-01", "justificativa": "Teste retroativo"},
        headers=pcm,
    )
    assert r.status_code == 422


def test_percentual_fora_da_faixa(client, pcm):
    p = _param(client, pcm, "tl_percentual")
    r = client.post(
        f"/api/v1/parametros/{p['id']}/vigencias",
        json={"valor": "6", "vigencia_inicio": "2027-01-01", "justificativa": "Digitado errado"},
        headers=pcm,
    )
    assert r.status_code == 422


def test_financeiro_nao_altera_parametro(client, financeiro):
    p = _param(client, financeiro, "tcif_valor_di")
    r = client.post(
        f"/api/v1/parametros/{p['id']}/vigencias",
        json={"valor": "1", "vigencia_inicio": "2027-01-01", "justificativa": "Sem permissão"},
        headers=financeiro,
    )
    assert r.status_code == 403


def test_aliquotas_e_componentes(client, pcm):
    a = client.get("/api/v1/aliquotas", headers=pcm).json()
    assert len(a["tipos"]) == 2
    assert {ln["imposto"]["codigo"] for ln in a["linhas"]} >= {"II", "ICMS"}
    comps = client.get("/api/v1/componentes", headers=pcm).json()
    assert comps[0]["codigo"] == "CIF"
    assert comps[0]["formula"]["expressao"] == "invoice_brl + frete_brl + siscomex"


def test_gestao_de_usuarios(client, admin, pcm):
    assert client.get("/api/v1/usuarios", headers=pcm).status_code == 403
    r = client.post(
        "/api/v1/usuarios",
        json={
            "nome": "Novo Analista",
            "email": "novo@forecast.local",
            "senha": "senha-forte-1",
            "perfis": ["FINANCEIRO"],
        },  # fmt: skip
        headers=admin,
    )
    assert r.status_code == 201, r.text
    login = client.post(
        "/api/v1/auth/login", json={"email": "novo@forecast.local", "senha": "senha-forte-1"}
    )
    assert login.status_code == 200
    assert "usuario:gerir" not in login.json()["permissoes"]

    usuario = r.json()
    r = client.put(
        f"/api/v1/usuarios/{usuario['id']}",
        json={
            "nome": "Novo Analista",
            "email": "novo@forecast.local",
            "ativo": False,
            "perfis": ["FINANCEIRO"],
        },
        headers=admin,
    )
    assert r.status_code == 200
    login = client.post(
        "/api/v1/auth/login", json={"email": "novo@forecast.local", "senha": "senha-forte-1"}
    )
    assert login.status_code == 401


def test_admin_nao_remove_proprio_acesso(client, admin):
    eu = client.get("/api/v1/auth/me", headers=admin).json()["usuario"]
    r = client.put(
        f"/api/v1/usuarios/{eu['id']}",
        json={"nome": eu["nome"], "email": eu["email"], "ativo": True, "perfis": ["PCM"]},
        headers=admin,
    )
    assert r.status_code == 422
