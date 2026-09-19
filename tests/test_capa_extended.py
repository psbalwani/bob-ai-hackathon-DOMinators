"""Extended tests for Track C's CAPA generator (src/capa/).

Complements tests/test_capa.py with unit-level coverage of every module:
  - templates.py  : worst_severity edge cases, all deviation types, unknown type
  - corpus.py     : load_ich_corpus, ich_chunks_for_deviation for every type,
                    ich_citation_string for both branch shapes, unknown chunk
                    defensive drop
  - store.py      : counter format, save/get round-trip, all_reports,
                    save_snapshot JSON validity, clear resets counter
  - export.py     : to_markdown section presence, to_pdf_bytes fallback when
                    fpdf2 is absent
  - generator.py  : invalid scope, empty deviations, cross-site rejection,
                    generated_at override, repeat-deviation count text,
                    multi-type cluster numbering, single-type multi-deviation
  - api (new paths): deviation-scope with empty deviation_ids list, site-scope
                    with a filtered deviation_ids subset, export of unknown
                    capa_id, site with no deviations returns 400

All tests exercise the deterministic templates.py path (no watsonx.ai
credentials required).
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from src.capa import corpus, generator, store
from src.capa.export import to_markdown, to_pdf_bytes
from src.capa.models import CapaReport, SCOPES
from src.capa.templates import (
    ActionSet,
    DUE_WINDOW_DAYS_BY_SEVERITY,
    OWNER_ROLE_BY_SEVERITY,
    for_deviation_type,
    worst_severity,
)

# ---------------------------------------------------------------------------
# Shared minimal fixtures (no filesystem dependency)
# ---------------------------------------------------------------------------

MINIMAL_PROTOCOL = {
    "protocol_id": "TRIAL-UNIT-TEST",
    "dosing_rules": {"drug": "TestDrug", "min_mg": 50, "max_mg": 200, "route": "oral"},
    "protocol_sections": [
        {"section_id": "3.1", "title": "Visit Schedule and Windows"},
        {"section_id": "4.1", "title": "Dosing Regimen"},
        {"section_id": "4.2", "title": "Prohibited Concomitant Medications"},
        {"section_id": "5.1", "title": "Required Procedures by Visit"},
        {"section_id": "6.3", "title": "Protocol Deviation Reporting"},
    ],
}


def _make_deviation(
    dev_id: str = "DEV-000001",
    site_id: str = "SITE-001",
    dev_type: str = "late_visit",
    severity: str = "Minor",
) -> dict:
    return {
        "deviation_id": dev_id,
        "site_id": site_id,
        "type": dev_type,
        "severity": severity,
        "severity_rationale": f"test rationale for {dev_type}",
        "protocol_clause_ref": "Section 3.1 - Visit Schedule and Windows",
    }


@pytest.fixture(scope="module")
def ich_corpus() -> dict[str, dict]:
    return corpus.load_ich_corpus()


# ===========================================================================
# templates.py
# ===========================================================================


class TestWorstSeverity:
    def test_single_major(self):
        assert worst_severity(["Major"]) == "Major"

    def test_single_minor(self):
        assert worst_severity(["Minor"]) == "Minor"

    def test_single_administrative(self):
        assert worst_severity(["Administrative"]) == "Administrative"

    def test_major_wins_over_minor_and_administrative(self):
        assert worst_severity(["Minor", "Administrative", "Major"]) == "Major"

    def test_minor_wins_over_administrative(self):
        assert worst_severity(["Administrative", "Minor"]) == "Minor"

    def test_all_same_returns_that_severity(self):
        assert worst_severity(["Minor", "Minor", "Minor"]) == "Minor"


class TestForDeviationType:
    """One smoke-test per known deviation type, plus error on unknown."""

    @pytest.mark.parametrize(
        "dev_type",
        ["banned_comedication", "dosage_out_of_range", "missed_visit", "late_visit"],
    )
    def test_known_types_return_action_set(self, dev_type):
        result = for_deviation_type(dev_type, "Minor", "SITE-001", MINIMAL_PROTOCOL)
        assert isinstance(result, ActionSet)
        assert result.root_cause.strip()
        assert result.corrective_action.strip()
        assert result.preventive_action.strip()
        # site_id should appear in narrative so text is site-specific
        assert "SITE-001" in result.root_cause

    def test_missing_procedure_major_mentions_consent(self):
        result = for_deviation_type("missing_procedure", "Major", "SITE-002", MINIMAL_PROTOCOL)
        assert "consent" in result.root_cause.lower()

    def test_missing_procedure_non_major_generic(self):
        for sev in ("Minor", "Administrative"):
            result = for_deviation_type("missing_procedure", sev, "SITE-003", MINIMAL_PROTOCOL)
            assert "consent" not in result.root_cause.lower()
            assert "procedure" in result.root_cause.lower()

    def test_unknown_type_raises_value_error(self):
        with pytest.raises(ValueError, match="No CAPA template"):
            for_deviation_type("alien_deviation", "Minor", "SITE-001", MINIMAL_PROTOCOL)

    def test_dosage_template_includes_range(self):
        result = for_deviation_type("dosage_out_of_range", "Major", "SITE-001", MINIMAL_PROTOCOL)
        assert "50" in result.root_cause
        assert "200" in result.root_cause

    def test_dosage_preventive_action_includes_range(self):
        result = for_deviation_type("dosage_out_of_range", "Major", "SITE-001", MINIMAL_PROTOCOL)
        assert "50" in result.preventive_action
        assert "200" in result.preventive_action


class TestOwnerAndDueWindowMappings:
    def test_major_owner_is_pi(self):
        assert OWNER_ROLE_BY_SEVERITY["Major"] == "Site Principal Investigator"

    def test_minor_owner_is_cra(self):
        assert OWNER_ROLE_BY_SEVERITY["Minor"] == "Clinical Research Associate (CRA)"

    def test_administrative_owner_is_coordinator(self):
        assert OWNER_ROLE_BY_SEVERITY["Administrative"] == "Site Coordinator"

    def test_major_due_window_is_7_days(self):
        assert DUE_WINDOW_DAYS_BY_SEVERITY["Major"] == 7

    def test_minor_due_window_is_14_days(self):
        assert DUE_WINDOW_DAYS_BY_SEVERITY["Minor"] == 14

    def test_administrative_due_window_is_21_days(self):
        assert DUE_WINDOW_DAYS_BY_SEVERITY["Administrative"] == 21


# ===========================================================================
# corpus.py
# ===========================================================================


class TestLoadIchCorpus:
    def test_returns_dict_keyed_by_chunk_id(self, ich_corpus):
        assert isinstance(ich_corpus, dict)
        for key, val in ich_corpus.items():
            assert key == val["chunk_id"]

    def test_noncompliance_chunk_present(self, ich_corpus):
        assert corpus.NONCOMPLIANCE_CHUNK_ID in ich_corpus

    def test_all_chunks_have_required_fields(self, ich_corpus):
        for chunk in ich_corpus.values():
            assert "chunk_id" in chunk
            assert "title" in chunk
            assert "ich_section" in chunk  # may be None


class TestIchChunksForDeviation:
    """Every deviation type should yield the noncompliance chunk plus its
    type-specific chunk; unknown types should still yield noncompliance."""

    @pytest.mark.parametrize(
        "dev_type,severity",
        [
            ("missed_visit", "Major"),
            ("late_visit", "Minor"),
            ("dosage_out_of_range", "Major"),
            ("banned_comedication", "Major"),
            ("missing_procedure", "Major"),
            ("missing_procedure", "Minor"),
            ("missing_procedure", "Administrative"),
        ],
    )
    def test_noncompliance_always_included(self, ich_corpus, dev_type, severity):
        chunks = corpus.ich_chunks_for_deviation(ich_corpus, dev_type, severity)
        ids = [c["chunk_id"] for c in chunks]
        assert corpus.NONCOMPLIANCE_CHUNK_ID in ids

    def test_unknown_type_still_returns_noncompliance(self, ich_corpus):
        chunks = corpus.ich_chunks_for_deviation(ich_corpus, "unknown_type", "Minor")
        ids = [c["chunk_id"] for c in chunks]
        assert corpus.NONCOMPLIANCE_CHUNK_ID in ids

    def test_result_contains_only_real_corpus_chunks(self, ich_corpus):
        """Defensive drop: no chunk returned should be absent from corpus."""
        for dev_type in ["missed_visit", "dosage_out_of_range", "missing_procedure"]:
            for sev in ["Major", "Minor", "Administrative"]:
                chunks = corpus.ich_chunks_for_deviation(ich_corpus, dev_type, sev)
                for chunk in chunks:
                    assert chunk["chunk_id"] in ich_corpus

    def test_no_duplicate_chunks_returned(self, ich_corpus):
        chunks = corpus.ich_chunks_for_deviation(ich_corpus, "missed_visit", "Major")
        ids = [c["chunk_id"] for c in chunks]
        assert len(ids) == len(set(ids))

    def test_missing_procedure_major_uses_consent_chunk(self, ich_corpus):
        chunks = corpus.ich_chunks_for_deviation(ich_corpus, "missing_procedure", "Major")
        ids = [c["chunk_id"] for c in chunks]
        assert "ICH-E6R2-4.8-INFORMED-CONSENT" in ids

    def test_missing_procedure_non_major_uses_records_chunk(self, ich_corpus):
        for sev in ("Minor", "Administrative"):
            chunks = corpus.ich_chunks_for_deviation(ich_corpus, "missing_procedure", sev)
            ids = [c["chunk_id"] for c in chunks]
            assert "ICH-E6R2-4.9-RECORDS-REPORTS" in ids

    def test_corpus_with_unknown_chunk_id_drops_gracefully(self):
        """If the corpus is missing an expected chunk_id it is silently dropped."""
        sparse_corpus = {corpus.NONCOMPLIANCE_CHUNK_ID: {"chunk_id": corpus.NONCOMPLIANCE_CHUNK_ID, "title": "x", "ich_section": "5.20"}}
        chunks = corpus.ich_chunks_for_deviation(sparse_corpus, "dosage_out_of_range", "Major")
        ids = [c["chunk_id"] for c in chunks]
        # only the noncompliance chunk should appear; the type-specific one is absent
        assert all(cid in sparse_corpus for cid in ids)


class TestIchCitationString:
    def test_with_ich_section_includes_section_number(self, ich_corpus):
        chunk = ich_corpus[corpus.NONCOMPLIANCE_CHUNK_ID]
        result = corpus.ich_citation_string(chunk)
        assert "5.20" in result
        assert "ICH E6(R2)" in result

    def test_without_ich_section_uses_internal_prefix(self, ich_corpus):
        # Taxonomy chunks have ich_section=None
        taxonomy_chunk = next(c for c in ich_corpus.values() if c["ich_section"] is None)
        result = corpus.ich_citation_string(taxonomy_chunk)
        assert result.startswith("Internal taxonomy note")
        assert taxonomy_chunk["title"] in result


# ===========================================================================
# store.py
# ===========================================================================


@pytest.fixture(autouse=True)
def reset_store():
    """Ensure every test starts with a fresh store."""
    store.clear()
    yield
    store.clear()


class TestStore:
    def _make_report(self, capa_id: str = "CAPA-000001") -> CapaReport:
        return CapaReport(
            capa_id=capa_id,
            scope="deviation",
            site_id="SITE-001",
            related_deviation_ids=["DEV-000001"],
            root_cause="root",
            corrective_action="correct",
            preventive_action="prevent",
            suggested_owner_role="Site Coordinator",
            suggested_due_window_days=21,
            generated_at="2026-01-01T00:00:00Z",
            evidence_citations=["DEV-000001"],
        )

    def test_next_capa_id_format(self):
        cid = store.next_capa_id()
        assert cid == "CAPA-000001"

    def test_next_capa_id_increments(self):
        ids = [store.next_capa_id() for _ in range(3)]
        assert ids == ["CAPA-000001", "CAPA-000002", "CAPA-000003"]

    def test_clear_resets_counter(self):
        store.next_capa_id()
        store.next_capa_id()
        store.clear()
        assert store.next_capa_id() == "CAPA-000001"

    def test_save_and_get_round_trip(self):
        report = self._make_report("CAPA-000001")
        store.save(report)
        fetched = store.get("CAPA-000001")
        assert fetched is report

    def test_get_unknown_returns_none(self):
        assert store.get("CAPA-999999") is None

    def test_all_reports_returns_saved_reports(self):
        r1 = self._make_report("CAPA-000001")
        r2 = self._make_report("CAPA-000002")
        store.save(r1)
        store.save(r2)
        assert set(r.capa_id for r in store.all_reports()) == {"CAPA-000001", "CAPA-000002"}

    def test_all_reports_empty_after_clear(self):
        store.save(self._make_report())
        store.clear()
        assert store.all_reports() == []

    def test_save_snapshot_writes_valid_json(self):
        store.save(self._make_report("CAPA-000001"))
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reports.json"
            store.save_snapshot(path)
            data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["capa_id"] == "CAPA-000001"

    def test_save_snapshot_empty_store_writes_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "reports.json"
            store.save_snapshot(path)
            data = json.loads(path.read_text(encoding="utf-8"))
        assert data == []

    def test_save_snapshot_creates_parent_dirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "reports.json"
            store.save_snapshot(path)
            assert path.exists()


# ===========================================================================
# export.py
# ===========================================================================


@pytest.fixture()
def sample_report() -> CapaReport:
    return CapaReport(
        capa_id="CAPA-EXP-001",
        scope="deviation",
        site_id="SITE-007",
        related_deviation_ids=["DEV-000042"],
        root_cause="The root cause text.",
        corrective_action="The corrective action text.",
        preventive_action="The preventive action text.",
        suggested_owner_role="Site Principal Investigator",
        suggested_due_window_days=7,
        generated_at="2026-06-15T10:00:00Z",
        evidence_citations=["DEV-000042", "Section 4.2 - Prohibited Concomitant Medications"],
    )


class TestToMarkdown:
    def test_contains_capa_id(self, sample_report):
        md = to_markdown(sample_report)
        assert "CAPA-EXP-001" in md

    def test_contains_root_cause_heading(self, sample_report):
        md = to_markdown(sample_report)
        assert "Root Cause" in md

    def test_contains_corrective_action_heading(self, sample_report):
        md = to_markdown(sample_report)
        assert "Corrective Action" in md

    def test_contains_preventive_action_heading(self, sample_report):
        md = to_markdown(sample_report)
        assert "Preventive Action" in md

    def test_contains_site_id(self, sample_report):
        md = to_markdown(sample_report)
        assert "SITE-007" in md

    def test_contains_deviation_id(self, sample_report):
        md = to_markdown(sample_report)
        assert "DEV-000042" in md

    def test_contains_all_citations(self, sample_report):
        md = to_markdown(sample_report)
        for citation in sample_report.evidence_citations:
            assert citation in md

    def test_contains_ownership_section(self, sample_report):
        md = to_markdown(sample_report)
        assert "Ownership" in md
        assert "7 days" in md

    def test_returns_string(self, sample_report):
        assert isinstance(to_markdown(sample_report), str)


class TestToPdfBytes:
    def test_returns_none_when_fpdf2_absent(self, sample_report):
        """When fpdf2 is not installed, to_pdf_bytes must return None (never raise)."""
        with patch.dict("sys.modules", {"fpdf": None}):
            result = to_pdf_bytes(sample_report)
        assert result is None

    def test_never_raises_regardless_of_fpdf2(self, sample_report):
        """Even with fpdf2 absent, no exception should propagate."""
        with patch.dict("sys.modules", {"fpdf": None}):
            try:
                to_pdf_bytes(sample_report)
            except Exception as exc:
                pytest.fail(f"to_pdf_bytes raised unexpectedly: {exc}")


# ===========================================================================
# generator.py  (unit-level, no filesystem required)
# ===========================================================================


class TestGeneratorValidation:
    def test_invalid_scope_raises(self, ich_corpus):
        dev = _make_deviation()
        with pytest.raises(ValueError, match="unknown scope"):
            generator.generate("cluster", [dev], MINIMAL_PROTOCOL, ich_corpus, "CAPA-V-001")

    def test_empty_deviations_raises(self, ich_corpus):
        with pytest.raises(ValueError, match="at least one deviation"):
            generator.generate("deviation", [], MINIMAL_PROTOCOL, ich_corpus, "CAPA-V-002")

    def test_deviation_scope_requires_exactly_one(self, ich_corpus):
        devs = [_make_deviation("DEV-1"), _make_deviation("DEV-2")]
        with pytest.raises(ValueError, match="exactly one"):
            generator.generate("deviation", devs, MINIMAL_PROTOCOL, ich_corpus, "CAPA-V-003")

    def test_cross_site_deviations_raises(self, ich_corpus):
        dev_a = _make_deviation("DEV-A", site_id="SITE-001")
        dev_b = _make_deviation("DEV-B", site_id="SITE-002")
        with pytest.raises(ValueError, match="one site_id"):
            generator.generate("site", [dev_a, dev_b], MINIMAL_PROTOCOL, ich_corpus, "CAPA-V-004")


class TestGeneratorOutput:
    def test_generated_at_override_is_respected(self, ich_corpus):
        dev = _make_deviation()
        ts = "2030-12-31T23:59:59Z"
        report = generator.generate("deviation", [dev], MINIMAL_PROTOCOL, ich_corpus, "CAPA-GA-001", generated_at=ts)
        assert report.generated_at == ts

    def test_generated_at_defaults_to_non_empty_string(self, ich_corpus):
        dev = _make_deviation()
        report = generator.generate("deviation", [dev], MINIMAL_PROTOCOL, ich_corpus, "CAPA-GA-002")
        assert report.generated_at.strip()

    def test_single_type_multi_deviation_appends_count(self, ich_corpus):
        """When >1 deviation with the same type, root_cause must include the count."""
        devs = [
            _make_deviation("DEV-1", dev_type="late_visit"),
            _make_deviation("DEV-2", dev_type="late_visit"),
            _make_deviation("DEV-3", dev_type="late_visit"),
        ]
        report = generator.generate("site", devs, MINIMAL_PROTOCOL, ich_corpus, "CAPA-MC-001")
        assert "3" in report.root_cause

    def test_multi_type_corrective_actions_are_numbered(self, ich_corpus):
        """Multi-type site reports must number each corrective/preventive action."""
        devs = [
            _make_deviation("DEV-A", dev_type="late_visit", severity="Minor"),
            _make_deviation("DEV-B", dev_type="missed_visit", severity="Major"),
        ]
        report = generator.generate("site", devs, MINIMAL_PROTOCOL, ich_corpus, "CAPA-MT-001")
        assert "1." in report.corrective_action
        assert "2." in report.corrective_action
        assert "1." in report.preventive_action
        assert "2." in report.preventive_action

    def test_multi_type_root_cause_mentions_mix(self, ich_corpus):
        devs = [
            _make_deviation("DEV-A", dev_type="late_visit", severity="Minor"),
            _make_deviation("DEV-B", dev_type="missed_visit", severity="Major"),
        ]
        report = generator.generate("site", devs, MINIMAL_PROTOCOL, ich_corpus, "CAPA-MT-002")
        assert "late_visit" in report.root_cause
        assert "missed_visit" in report.root_cause

    def test_worst_severity_selects_major_owner(self, ich_corpus):
        devs = [
            _make_deviation("DEV-A", dev_type="late_visit", severity="Administrative"),
            _make_deviation("DEV-B", dev_type="banned_comedication", severity="Major"),
        ]
        devs[1]["protocol_clause_ref"] = "Section 4.2 - Prohibited Concomitant Medications"
        report = generator.generate("site", devs, MINIMAL_PROTOCOL, ich_corpus, "CAPA-SEV-001")
        assert report.suggested_owner_role == "Site Principal Investigator"
        assert report.suggested_due_window_days == 7

    def test_administrative_only_gets_coordinator_owner(self, ich_corpus):
        dev = _make_deviation(dev_type="late_visit", severity="Administrative")
        report = generator.generate("deviation", [dev], MINIMAL_PROTOCOL, ich_corpus, "CAPA-SEV-002")
        assert report.suggested_owner_role == "Site Coordinator"
        assert report.suggested_due_window_days == 21

    def test_capa_id_propagated(self, ich_corpus):
        dev = _make_deviation()
        report = generator.generate("deviation", [dev], MINIMAL_PROTOCOL, ich_corpus, "CAPA-ID-XYZ")
        assert report.capa_id == "CAPA-ID-XYZ"

    def test_scope_propagated(self, ich_corpus):
        dev = _make_deviation()
        report = generator.generate("deviation", [dev], MINIMAL_PROTOCOL, ich_corpus, "CAPA-SC-001")
        assert report.scope == "deviation"

    def test_deviation_scope_report_has_one_related_id(self, ich_corpus):
        dev = _make_deviation("DEV-SOLO")
        report = generator.generate("deviation", [dev], MINIMAL_PROTOCOL, ich_corpus, "CAPA-SC-002")
        assert report.related_deviation_ids == ["DEV-SOLO"]

    def test_all_deviation_ids_in_related_ids_for_site_scope(self, ich_corpus):
        devs = [_make_deviation(f"DEV-{i:03d}") for i in range(1, 5)]
        report = generator.generate("site", devs, MINIMAL_PROTOCOL, ich_corpus, "CAPA-SC-003")
        assert set(report.related_deviation_ids) == {d["deviation_id"] for d in devs}


# ===========================================================================
# models.py
# ===========================================================================


class TestModels:
    def test_scopes_contains_expected_values(self):
        assert "deviation" in SCOPES
        assert "site" in SCOPES

    def test_to_dict_returns_all_fields(self):
        report = CapaReport(
            capa_id="CAPA-000001",
            scope="deviation",
            site_id="SITE-001",
            related_deviation_ids=["DEV-000001"],
            root_cause="r",
            corrective_action="c",
            preventive_action="p",
            suggested_owner_role="Site Coordinator",
            suggested_due_window_days=21,
            generated_at="2026-01-01T00:00:00Z",
        )
        d = report.to_dict()
        expected_keys = {
            "capa_id", "scope", "site_id", "related_deviation_ids",
            "root_cause", "corrective_action", "preventive_action",
            "suggested_owner_role", "suggested_due_window_days",
            "generated_at", "evidence_citations", "protocol_id",
        }
        assert set(d.keys()) == expected_keys

    def test_evidence_citations_defaults_to_empty_list(self):
        report = CapaReport(
            capa_id="X", scope="deviation", site_id="S",
            related_deviation_ids=[], root_cause="",
            corrective_action="", preventive_action="",
            suggested_owner_role="", suggested_due_window_days=0,
            generated_at="",
        )
        assert report.evidence_citations == []


# ===========================================================================
# API — additional paths not covered by test_capa.py
# ===========================================================================

SYNTHETIC_DIR = Path("data/synthetic")

pytestmark = pytest.mark.skipif(
    not (SYNTHETIC_DIR / "protocol.json").exists(),
    reason="data/synthetic/ not generated -- run src/data/generate_synthetic_data.py first",
)


@pytest.fixture()
def client():
    store.clear()
    from src.capa.api import app
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def real_deviations_mod():
    import json as _json
    from src.detection.detector import detect_deviations

    protocol = _json.loads((SYNTHETIC_DIR / "protocol.json").read_text(encoding="utf-8"))
    visit_records = _json.loads((SYNTHETIC_DIR / "visit_records.json").read_text(encoding="utf-8"))
    return [d.to_dict() for d in detect_deviations(protocol, visit_records)]


class TestApiAdditionalPaths:
    def test_deviation_scope_with_empty_deviation_ids_is_validation_error(self, client):
        resp = client.post("/capa/generate", json={"scope": "deviation", "deviation_ids": []})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_site_scope_without_site_id_is_validation_error(self, client):
        resp = client.post("/capa/generate", json={"scope": "site"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_site_scope_with_filtered_deviation_ids(self, client, real_deviations_mod):
        """site + deviation_ids subset: should produce a report covering only the
        requested IDs (not all deviations at that site)."""
        from collections import defaultdict
        by_site: dict = defaultdict(list)
        for d in real_deviations_mod:
            by_site[d["site_id"]].append(d)
        site_id, devs = max(by_site.items(), key=lambda kv: len(kv[1]))
        subset_id = devs[0]["deviation_id"]

        resp = client.post(
            "/capa/generate",
            json={"scope": "site", "site_id": site_id, "deviation_ids": [subset_id]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["related_deviation_ids"] == [subset_id]

    def test_site_scope_with_unknown_deviation_id_is_not_found(self, client, real_deviations_mod):
        from collections import defaultdict
        by_site: dict = defaultdict(list)
        for d in real_deviations_mod:
            by_site[d["site_id"]].append(d)
        site_id = next(iter(by_site))

        resp = client.post(
            "/capa/generate",
            json={"scope": "site", "site_id": site_id, "deviation_ids": ["DEV-GHOST-99"]},
        )
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_export_unknown_capa_id_is_not_found(self, client):
        resp = client.get("/capa/CAPA-GHOST/export", params={"format": "markdown"})
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "NOT_FOUND"

    def test_export_markdown_contains_all_report_fields(self, client, real_deviations_mod):
        dev_id = real_deviations_mod[0]["deviation_id"]
        generated = client.post(
            "/capa/generate", json={"scope": "deviation", "deviation_ids": [dev_id]}
        ).json()
        resp = client.get(f"/capa/{generated['capa_id']}/export", params={"format": "markdown"})
        assert resp.status_code == 200
        text = resp.text
        assert generated["site_id"] in text
        assert generated["root_cause"] in text
        assert generated["corrective_action"] in text
        assert generated["preventive_action"] in text

    def test_multiple_generate_calls_produce_distinct_capa_ids(self, client, real_deviations_mod):
        ids = []
        for dev in real_deviations_mod[:3]:
            resp = client.post(
                "/capa/generate", json={"scope": "deviation", "deviation_ids": [dev["deviation_id"]]}
            )
            assert resp.status_code == 200
            ids.append(resp.json()["capa_id"])
        assert len(set(ids)) == 3
