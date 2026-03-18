import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from oventime.cache import cache
from oventime.api.routes import app
from oventime.utils import floor_dt


# ── Fixture ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Redirige le cache vers une base temporaire pour chaque test."""
    cache.DB_PATH = tmp_path / "cache.sqlite"
    cache.init_db()


@pytest.fixture
def client():
    """Crée un client de test FastAPI (simule des requêtes sans réseau)."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _set_internal_token(monkeypatch):
    """Force le token admin à une valeur connue, quel que soit le .env local."""
    monkeypatch.setattr("oventime.api.routes.INTERNAL_API_TOKEN", "test_token")


@pytest.fixture
def auth_headers():
    """Headers avec le token admin pour les endpoints protégés."""
    return {"x-internal-token": "test_token"}


# ── Helper ───────────────────────────────────────────────────────────────────

def insert_sample_data():
    """Insère un diagnostic de test dans le cache."""
    now = floor_dt(datetime.now(timezone.utc))
    cache.save({
        "time": now,
        "status": "green",
        "score": 75.0,
        "nuclear_bonus": 0.0,
        "ocgt_malus": 0.0,
        "gasCCG_use_rate": 0.2,
        "gasCCG_phase": 0.3,
        "storage_phase": 0.1,
        "storage_use_rate": 0.15,
        "nuclear_use_rate": 0.8,
        "nextwind_start": now + timedelta(hours=2),
        "nextwind_end": now + timedelta(hours=5),
        "nextwind_method": "otsu",
    })


# ── Tests endpoints publics ─────────────────────────────────────────────────

def test_status_empty_returns_404(client):
    """Base vide → pas de données → 404."""
    r = client.get("/status")
    assert r.status_code == 404


def test_status_with_data_returns_200(client):
    """Avec des données en cache → 200 + contenu."""
    insert_sample_data()
    r = client.get("/status")
    assert r.status_code == 200
    assert r.json()["status"] == "green"


def test_diagnostic_empty_returns_404(client):
    r = client.get("/diagnostic")
    assert r.status_code == 404


def test_diagnostic_with_data_returns_score(client):
    insert_sample_data()
    r = client.get("/diagnostic")
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == pytest.approx(75.0)
    assert "details" in data


def test_next_window_empty_returns_404(client):
    r = client.get("/next/window")
    assert r.status_code == 404


def test_next_window_with_data(client):
    insert_sample_data()
    r = client.get("/next/window")
    assert r.status_code == 200
    data = r.json()
    assert "nextwind_start" in data
    assert "nextwind_end" in data


def test_vapid_public_key(client):
    """Cet endpoint ne dépend d'aucune donnée, il retourne toujours la clé."""
    r = client.get("/vapid-public-key")
    assert r.status_code == 200
    assert "publicKey" in r.json()


# ── Tests endpoints admin (auth) ────────────────────────────────────────────

def test_admin_without_token_returns_401(client):
    """Sans token → rejeté."""
    r = client.get("/tsubs")
    assert r.status_code == 401


def test_admin_with_bad_token_returns_401(client):
    """Mauvais token → rejeté aussi."""
    r = client.get("/tsubs", headers={"x-internal-token": "wrong"})
    assert r.status_code == 401


def test_admin_tsubs_crud(client, auth_headers):
    """Cycle complet : lister → ajouter → vérifier → supprimer → vérifier."""
    r = client.get("/tsubs", headers=auth_headers)
    assert r.json()["chat_ids"] == []

    r = client.post("/tsubs/12345", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["chat_id"] == 12345

    r = client.get("/tsubs", headers=auth_headers)
    assert 12345 in r.json()["chat_ids"]

    r = client.delete("/tsubs/12345", headers=auth_headers)
    assert r.status_code == 200

    r = client.get("/tsubs", headers=auth_headers)
    assert 12345 not in r.json()["chat_ids"]


def test_admin_tables_blocked_name(client, auth_headers):
    """Vérifie que la whitelist ALLOWED_TABLES bloque les noms inconnus."""
    r = client.get("/admin/tables/secret_table", headers=auth_headers)
    assert r.status_code == 404


def test_wsubs_invalid_body_returns_400(client):
    """Subscription sans les bons champs → 400."""
    r = client.post("/wsubs", json={"endpoint": ""})
    assert r.status_code == 400
