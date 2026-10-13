import os

# Precisa vir antes de qualquer import de app.*
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://forecast:forecast_dev@localhost:5433/forecast_test"
)
os.environ.setdefault("SEED_SENHA", "senha-de-teste-123")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.db import SessionLocal, engine  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SENHA = os.environ["SEED_SENHA"]


@pytest.fixture(scope="session", autouse=True)
def banco():
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.set_main_option("script_location", str(RAIZ / "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    cfg.attributes["configurar_logging"] = False
    command.upgrade(cfg, "head")

    from app.seed import seed_base

    with SessionLocal() as db:
        seed_base(db)
        db.commit()
    yield


@pytest.fixture(scope="session")
def client(banco):
    from app.main import app

    return TestClient(app)


def _token(client: TestClient, email: str) -> dict[str, str]:
    r = client.post("/api/v1/auth/login", json={"email": email, "senha": SENHA})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="session")
def pcm(client):
    return _token(client, "pcm@forecast.local")


@pytest.fixture(scope="session")
def financeiro(client):
    return _token(client, "financeiro@forecast.local")


@pytest.fixture(scope="session")
def admin(client):
    return _token(client, "admin@forecast.local")


@pytest.fixture(scope="session")
def refs(client, pcm):
    tipos = {
        t["codigo"]: t["id"] for t in client.get("/api/v1/tipos-importacao", headers=pcm).json()
    }
    transp = {t["nome"]: t["id"] for t in client.get("/api/v1/transportadoras", headers=pcm).json()}
    desp = client.get("/api/v1/despachantes", headers=pcm).json()
    term = {t["nome"]: t["id"] for t in client.get("/api/v1/terminais", headers=pcm).json()}
    return {"tipos": tipos, "transp": transp, "despachante": desp[0]["id"], "term": term}
