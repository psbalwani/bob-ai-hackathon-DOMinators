"""Tests for the multi-drug gateway (src/backend/app/main.py): per-protocol
dataset isolation, drug-owner login, and ownership enforcement.

Uses the real generated data/synthetic/ dataset (the primary protocol plus
its data/synthetic/drugs/ siblings) rather than mocks, so this exercises
the actual startup discovery + auth wiring end to end.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.backend.app.main import app

SYNTHETIC_DIR = Path("data/synthetic")

pytestmark = pytest.mark.skipif(
    not (SYNTHETIC_DIR / "drugs").exists(),
    reason="multi-drug dataset not generated -- run src/data/generate_synthetic_data.py first",
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, username: str, password: str = "changeme123") -> dict:
    resp = client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_owned_protocols(client):
    body = _login(client, "owner_onc04")
    assert body["user"]["protocols"] == [
        {"protocol_id": "TRIAL-2026-ONC-04", "title": "Phase III Oncology Trial - Drug X", "drug": "Drug X"}
    ]
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_wrong_password_is_unauthorized(client):
    resp = client.post("/auth/login", json={"username": "owner_onc04", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_no_token_is_unauthorized(client):
    resp = client.get("/dashboard/summary", params={"protocol_id": "TRIAL-2026-ONC-04"})
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_owner_sees_only_their_own_protocol(client):
    onc04 = _login(client, "owner_onc04")
    onc05 = _login(client, "owner_onc05")

    resp = client.get(
        "/dashboard/summary",
        params={"protocol_id": "TRIAL-2026-ONC-04"},
        headers=_auth_headers(onc04["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["protocol_id"] == "TRIAL-2026-ONC-04"

    # onc04's owner requesting onc05's protocol -> 403, not data leakage
    resp = client.get(
        "/dashboard/summary",
        params={"protocol_id": "TRIAL-2026-ONC-05"},
        headers=_auth_headers(onc04["access_token"]),
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    resp = client.get(
        "/dashboard/summary",
        params={"protocol_id": "TRIAL-2026-ONC-05"},
        headers=_auth_headers(onc05["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["protocol_id"] == "TRIAL-2026-ONC-05"


def test_unknown_protocol_id_is_not_found(client):
    onc04 = _login(client, "owner_onc04")
    resp = client.get(
        "/dashboard/summary",
        params={"protocol_id": "NOT-A-REAL-PROTOCOL"},
        headers=_auth_headers(onc04["access_token"]),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_portfolio_owner_sees_every_protocol(client):
    portfolio = _login(client, "owner_portfolio")
    assert len(portfolio["user"]["protocols"]) == 10


def test_shared_site_scores_independently_per_protocol(client):
    """A site that hosts patients under two different protocols must get an
    independent risk score for each -- proof that a site isn't accidentally
    a single global resource once protocols share the pool."""
    portfolio = _login(client, "owner_portfolio")
    headers = _auth_headers(portfolio["access_token"])

    sites04 = {
        s["site_id"]
        for s in client.get("/sites", params={"protocol_id": "TRIAL-2026-ONC-04"}, headers=headers).json()["sites"]
    }
    sites05 = {
        s["site_id"]
        for s in client.get("/sites", params={"protocol_id": "TRIAL-2026-ONC-05"}, headers=headers).json()["sites"]
    }
    shared = sorted(sites04 & sites05)
    assert shared, "expected at least one site shared between two protocols"

    site_id = shared[0]
    detail_04 = client.get(f"/sites/{site_id}", params={"protocol_id": "TRIAL-2026-ONC-04"}, headers=headers).json()
    detail_05 = client.get(f"/sites/{site_id}", params={"protocol_id": "TRIAL-2026-ONC-05"}, headers=headers).json()
    assert detail_04["risk_score"]["protocol_id"] == "TRIAL-2026-ONC-04"
    assert detail_05["risk_score"]["protocol_id"] == "TRIAL-2026-ONC-05"


def test_capa_ownership_is_enforced(client):
    onc04 = _login(client, "owner_onc04")
    onc05 = _login(client, "owner_onc05")

    sites = client.get(
        "/sites", params={"protocol_id": "TRIAL-2026-ONC-04"}, headers=_auth_headers(onc04["access_token"])
    ).json()["sites"]
    site_id = sites[0]["site_id"]

    resp = client.post(
        "/capa/generate",
        json={"protocol_id": "TRIAL-2026-ONC-04", "scope": "site", "site_id": site_id},
        headers=_auth_headers(onc04["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    capa_id = resp.json()["capa_id"]

    # another drug's owner can't read it
    resp = client.get(f"/capa/{capa_id}", headers=_auth_headers(onc05["access_token"]))
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # the owning drug's owner can
    resp = client.get(f"/capa/{capa_id}", headers=_auth_headers(onc04["access_token"]))
    assert resp.status_code == 200


def test_deviation_lookup_enforces_ownership(client):
    onc04 = _login(client, "owner_onc04")
    onc05 = _login(client, "owner_onc05")

    devs = client.post(
        "/deviations/detect",
        json={"protocol_id": "TRIAL-2026-ONC-04"},
        headers=_auth_headers(onc04["access_token"]),
    ).json()["deviations"]
    assert devs
    deviation_id = devs[0]["deviation_id"]

    resp = client.get(f"/deviations/{deviation_id}", headers=_auth_headers(onc05["access_token"]))
    assert resp.status_code == 403

    resp = client.get(f"/deviations/{deviation_id}", headers=_auth_headers(onc04["access_token"]))
    assert resp.status_code == 200
    assert resp.json()["deviation"]["deviation_id"] == deviation_id
