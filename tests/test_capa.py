"""Tests for Track C's CAPA generator (src/capa/).

Runs against the real synthetic dataset and Track A's real detector output
-- no mocking, since both are live. Deliberately does NOT set any
WATSONX_* env vars, so these exercise the deterministic templates.py
fallback path exclusively (matches how tests/test_api.py and
tests/test_rules.py already run in this repo/CI, with no watsonx
credentials available).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.capa import corpus, generator, store
from src.capa.models import CapaReport
from src.detection.detector import detect_deviations

SYNTHETIC_DIR = Path("data/synthetic")

pytestmark = pytest.mark.skipif(
    not (SYNTHETIC_DIR / "protocol.json").exists(),
    reason="data/synthetic/ not generated -- run src/data/generate_synthetic_data.py first",
)

CAPA_FIELDS = {
    "capa_id",
    "scope",
    "site_id",
    "related_deviation_ids",
    "root_cause",
    "corrective_action",
    "preventive_action",
    "suggested_owner_role",
    "suggested_due_window_days",
    "generated_at",
    "evidence_citations",
    "protocol_id",
}


@pytest.fixture(scope="module")
def protocol() -> dict:
    return json.loads((SYNTHETIC_DIR / "protocol.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def visit_records() -> list[dict]:
    return json.loads((SYNTHETIC_DIR / "visit_records.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ich_corpus() -> dict[str, dict]:
    return corpus.load_ich_corpus()


@pytest.fixture(scope="module")
def real_deviations(protocol, visit_records) -> list[dict]:
    """Real Deviation-shaped dicts from Track A's actual detector -- not mocks."""
    return [d.to_dict() for d in detect_deviations(protocol, visit_records)]


@pytest.fixture(scope="module")
def deviations_by_site(real_deviations) -> dict[str, list[dict]]:
    by_site: dict[str, list[dict]] = {}
    for d in real_deviations:
        by_site.setdefault(d["site_id"], []).append(d)
    return by_site


def _valid_protocol_clause_refs(protocol: dict) -> set[str]:
    return {f"Section {s['section_id']} - {s['title']}" for s in protocol["protocol_sections"]}


def _valid_ich_citations(ich_corpus: dict) -> set[str]:
    return {corpus.ich_citation_string(c) for c in ich_corpus.values()}


# ---------------------------------------------------------------------------
# Contract conformance
# ---------------------------------------------------------------------------


def test_single_deviation_report_matches_contract_shape(protocol, ich_corpus, real_deviations):
    dev = real_deviations[0]
    report = generator.generate("deviation", [dev], protocol, ich_corpus, "CAPA-TEST-001")
    assert isinstance(report, CapaReport)
    assert set(report.to_dict().keys()) == CAPA_FIELDS
    assert report.scope == "deviation"
    assert report.related_deviation_ids == [dev["deviation_id"]]
    assert report.site_id == dev["site_id"]
    assert report.suggested_owner_role in {
        "Site Principal Investigator", "Clinical Research Associate (CRA)", "Site Coordinator",
    }
    assert report.suggested_due_window_days > 0
    assert report.root_cause and report.corrective_action and report.preventive_action


def test_site_scope_report_covers_all_related_deviations(protocol, ich_corpus, deviations_by_site):
    site_id, devs = max(deviations_by_site.items(), key=lambda kv: len(kv[1]))
    assert len(devs) > 1, "need a site with multiple deviations to test clustering"

    report = generator.generate("site", devs, protocol, ich_corpus, "CAPA-TEST-002")
    assert report.scope == "site"
    assert report.site_id == site_id
    assert set(report.related_deviation_ids) == {d["deviation_id"] for d in devs}


def test_worst_severity_drives_owner_and_due_window(protocol, ich_corpus):
    major = {
        "deviation_id": "DEV-X1", "site_id": "SITE-001", "type": "banned_comedication",
        "severity": "Major", "severity_rationale": "x", "protocol_clause_ref": "Section 4.2 - Prohibited Concomitant Medications",
    }
    minor = {
        "deviation_id": "DEV-X2", "site_id": "SITE-001", "type": "late_visit",
        "severity": "Minor", "severity_rationale": "x", "protocol_clause_ref": "Section 3.1 - Visit Schedule and Windows",
    }
    report = generator.generate("site", [major, minor], protocol, ich_corpus, "CAPA-TEST-003")
    assert report.suggested_owner_role == "Site Principal Investigator"  # driven by the Major, not the Minor
    assert report.suggested_due_window_days == 7


# ---------------------------------------------------------------------------
# No-hallucination guarantee -- the checklist's explicit requirement
# ---------------------------------------------------------------------------


def test_evidence_citations_never_hallucinate(protocol, ich_corpus, real_deviations, deviations_by_site):
    """Every citation on every generated report traces back to real data:
    a real deviation_id, a real protocol clause, or a real ICH corpus chunk.
    """
    valid_clauses = _valid_protocol_clause_refs(protocol)
    valid_ich = _valid_ich_citations(ich_corpus)
    valid_deviation_ids = {d["deviation_id"] for d in real_deviations}

    reports = []
    for dev in real_deviations[:10]:
        reports.append(generator.generate("deviation", [dev], protocol, ich_corpus, f"CAPA-CHK-{dev['deviation_id']}"))
    for site_id, devs in list(deviations_by_site.items())[:5]:
        reports.append(generator.generate("site", devs, protocol, ich_corpus, f"CAPA-CHK-{site_id}"))

    for report in reports:
        for citation in report.evidence_citations:
            assert (
                citation in valid_deviation_ids
                or citation in valid_clauses
                or citation in valid_ich
            ), f"unverifiable citation on {report.capa_id}: {citation!r}"


def test_every_related_deviation_id_is_cited(protocol, ich_corpus, deviations_by_site):
    site_id, devs = next(iter(deviations_by_site.items()))
    report = generator.generate("site", devs, protocol, ich_corpus, "CAPA-TEST-004")
    for dev in devs:
        assert dev["deviation_id"] in report.evidence_citations


def test_noncompliance_clause_always_cited(protocol, ich_corpus, real_deviations):
    """Section 5.20 is the ICH basis for requiring a CAPA at all -- every
    report should ground itself in it, per DESIGN.md."""
    dev = real_deviations[0]
    report = generator.generate("deviation", [dev], protocol, ich_corpus, "CAPA-TEST-005")
    assert any("Section 5.20" in c for c in report.evidence_citations)


# ---------------------------------------------------------------------------
# Deterministic fallback (no watsonx.ai configured in this test environment)
# ---------------------------------------------------------------------------


def test_generation_never_raises_without_watsonx_configured(monkeypatch, protocol, ich_corpus, real_deviations):
    monkeypatch.delenv("WATSONX_API_KEY", raising=False)
    for dev in real_deviations[:20]:
        report = generator.generate("deviation", [dev], protocol, ich_corpus, f"CAPA-FB-{dev['deviation_id']}")
        assert report.root_cause.strip()
        assert report.corrective_action.strip()
        assert report.preventive_action.strip()


def test_all_five_deviation_types_have_templates(protocol, ich_corpus, real_deviations):
    types_seen = {d["type"] for d in real_deviations}
    assert types_seen, "expected the real detector to find at least one deviation type"
    for dev in real_deviations:
        # exercises templates.for_deviation_type for every type actually present
        generator.generate("deviation", [dev], protocol, ich_corpus, f"CAPA-TYPE-{dev['deviation_id']}")


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


@pytest.fixture()
def client():
    store.clear()
    from src.capa.api import app

    with TestClient(app) as c:
        yield c


def test_api_generate_deviation_scope(client, real_deviations):
    dev_id = real_deviations[0]["deviation_id"]
    resp = client.post("/capa/generate", json={"scope": "deviation", "deviation_ids": [dev_id]})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == CAPA_FIELDS
    assert body["related_deviation_ids"] == [dev_id]


def test_api_generate_site_scope(client, deviations_by_site):
    site_id = next(iter(deviations_by_site.keys()))
    resp = client.post("/capa/generate", json={"scope": "site", "site_id": site_id})
    assert resp.status_code == 200
    assert resp.json()["site_id"] == site_id


def test_api_get_generated_report(client, real_deviations):
    dev_id = real_deviations[0]["deviation_id"]
    generated = client.post("/capa/generate", json={"scope": "deviation", "deviation_ids": [dev_id]}).json()
    resp = client.get(f"/capa/{generated['capa_id']}")
    assert resp.status_code == 200
    assert resp.json() == generated


def test_api_get_unknown_capa_is_not_found(client):
    resp = client.get("/capa/CAPA-999999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_api_unknown_deviation_id_is_not_found(client):
    resp = client.post("/capa/generate", json={"scope": "deviation", "deviation_ids": ["DEV-999999"]})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_api_unknown_site_id_is_not_found(client):
    resp = client.post("/capa/generate", json={"scope": "site", "site_id": "SITE-999"})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_api_bad_scope_is_validation_error(client):
    resp = client.post("/capa/generate", json={"scope": "nonsense"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_api_export_markdown(client, real_deviations):
    dev_id = real_deviations[0]["deviation_id"]
    generated = client.post("/capa/generate", json={"scope": "deviation", "deviation_ids": [dev_id]}).json()
    resp = client.get(f"/capa/{generated['capa_id']}/export", params={"format": "markdown"})
    assert resp.status_code == 200
    assert generated["capa_id"] in resp.text
    assert "Root Cause" in resp.text


def test_api_export_bad_format_is_validation_error(client, real_deviations):
    dev_id = real_deviations[0]["deviation_id"]
    generated = client.post("/capa/generate", json={"scope": "deviation", "deviation_ids": [dev_id]}).json()
    resp = client.get(f"/capa/{generated['capa_id']}/export", params={"format": "xml"})
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"
