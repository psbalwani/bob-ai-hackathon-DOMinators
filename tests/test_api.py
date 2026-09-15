"""FastAPI TestClient tests for the Track A endpoints (05_api_contracts.md)."""

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.detection.api import app

SYNTHETIC_DIR = Path("data/synthetic")

pytestmark = pytest.mark.skipif(
    not (SYNTHETIC_DIR / "protocol.json").exists(),
    reason="data/synthetic/ not generated -- run src/data/generate_synthetic_data.py first",
)

DEVIATION_FIELDS = {
    "deviation_id",
    "visit_record_id",
    "patient_id",
    "site_id",
    "protocol_id",
    "type",
    "severity",
    "severity_rationale",
    "protocol_clause_ref",
    "detected_at",
    "detector_version",
}


# BUG-11: module-scope fixture so the lifespan + full detection run happens once
# for the entire test session instead of 5 times (one per function-scope fixture).
# BUG-10: patch classify_late_visit_severity to return None (the "no credentials"
# fallback) so tests never make live watsonx.ai calls and never burn token quota.
@pytest.fixture(scope="module")
def client():
    with patch("src.detection.llm_hook.classify_late_visit_severity", return_value=None):
        with TestClient(app) as c:
            yield c


def test_detect_returns_deviation_shaped_objects(client):
    resp = client.post("/deviations/detect", json={"protocol_id": "TRIAL-2026-ONC-04"})
    assert resp.status_code == 200
    body = resp.json()
    assert "deviations" in body
    assert len(body["deviations"]) > 0
    assert set(body["deviations"][0].keys()) == DEVIATION_FIELDS


def test_detect_unknown_protocol_id_is_validation_error(client):
    resp = client.post("/deviations/detect", json={"protocol_id": "NOT-A-REAL-PROTOCOL"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_site_deviations_after_detect(client):
    client.post("/deviations/detect", json={"protocol_id": "TRIAL-2026-ONC-04"})
    resp = client.get("/deviations/site/SITE-001")
    assert resp.status_code == 200
    assert "deviations" in resp.json()


def test_get_unknown_site_is_not_found(client):
    resp = client.get("/deviations/site/SITE-999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_detect_scoped_to_specific_visit_record_ids(client):
    all_devs = client.post("/deviations/detect", json={"protocol_id": "TRIAL-2026-ONC-04"}).json()[
        "deviations"
    ]
    one_record_id = all_devs[0]["visit_record_id"]
    resp = client.post(
        "/deviations/detect",
        json={"protocol_id": "TRIAL-2026-ONC-04", "visit_record_ids": [one_record_id]},
    )
    assert resp.status_code == 200
    scoped = resp.json()["deviations"]
    assert all(d["visit_record_id"] == one_record_id for d in scoped)
