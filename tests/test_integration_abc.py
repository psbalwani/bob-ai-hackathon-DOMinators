"""Cross-track integration tests: A → B → C end-to-end pipeline.

These tests exercise the real data flow between all three tracks using the
live synthetic dataset (data/synthetic/).  No mocks — each stage receives
the real output of the previous one:

  Track A  detect_deviations(protocol, visit_records) → list[Deviation]
      ↓
  Track B  compute_site_risk_score / rank_sites(deviations, ...) → RiskScore
      ↓
  Track C  generator.generate(deviations, ...) → CapaReport

The seams between tracks (shared data contracts in docs/04_data_schema.md) are
verified explicitly:

  A→B  Deviation dicts emitted by Track A are accepted by Track B's scorer
       without transformation; high-seeded sites rank above low-seeded ones.
  A→C  Deviation dicts emitted by Track A are accepted by Track C's generator;
       no-hallucination guarantee holds end-to-end (every evidence citation
       traces to real data A produced, real protocol clauses, or real ICH chunks).
  B→C  The site Track B scores highest is one Track C can generate a full
       report for; severity-driven owner/due-window from C matches the worst
       severity Track A found at that site.
  Full A→B→C  The entire pipeline runs on every site without raising an
       exception; every CAPA report is complete and fully populated.

Skip condition: data/synthetic/ must exist (run generate_synthetic_data.py).
No watsonx.ai credentials required — deterministic templates.py path only.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.capa import corpus, generator
from src.capa.models import CapaReport
from src.capa.templates import DUE_WINDOW_DAYS_BY_SEVERITY, OWNER_ROLE_BY_SEVERITY
from src.detection.detector import detect_deviations
from src.detection.models import DEVIATION_TYPES, SEVERITIES
from src.risk_scoring.scoring import compute_site_risk_score, rank_sites

SYNTHETIC_DIR = Path("data/synthetic")

pytestmark = pytest.mark.skipif(
    not (SYNTHETIC_DIR / "protocol.json").exists(),
    reason="data/synthetic/ not generated -- run src/data/generate_synthetic_data.py first",
)

# ---------------------------------------------------------------------------
# Module-scoped fixtures  (shared across all test classes; run once per session)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def protocol() -> dict:
    return json.loads((SYNTHETIC_DIR / "protocol.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def visit_records() -> list[dict]:
    return json.loads((SYNTHETIC_DIR / "visit_records.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sites() -> list[dict]:
    return json.loads((SYNTHETIC_DIR / "sites.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ich_corpus() -> dict[str, dict]:
    return corpus.load_ich_corpus()


@pytest.fixture(scope="module")
def detected_deviations(protocol, visit_records) -> list[dict]:
    """Track A's real output — used as input for both Track B and Track C."""
    return [d.to_dict() for d in detect_deviations(protocol, visit_records)]


@pytest.fixture(scope="module")
def deviations_by_site(detected_deviations) -> dict[str, list[dict]]:
    by_site: dict[str, list[dict]] = {}
    for d in detected_deviations:
        by_site.setdefault(d["site_id"], []).append(d)
    return by_site


@pytest.fixture(scope="module")
def site_ids(sites) -> list[str]:
    return [s["site_id"] for s in sites]


@pytest.fixture(scope="module")
def risk_ranking(protocol, detected_deviations, visit_records, site_ids) -> list[dict]:
    """Track B's full ranking computed from Track A's real output."""
    return rank_sites(
        protocol["protocol_id"],
        detected_deviations,
        visit_records,
        protocol["visit_schedule"],
        site_ids,
    )


# ---------------------------------------------------------------------------
# A → B: Deviation contract → Risk Scoring
# ---------------------------------------------------------------------------


class TestTrackAToTrackB:
    def test_track_a_output_feeds_track_b_without_error(
        self, protocol, detected_deviations, visit_records, site_ids
    ):
        """Track B must accept Track A's raw deviation dicts without any
        transformation layer in between."""
        for site_id in site_ids[:5]:
            score = compute_site_risk_score(
                site_id,
                protocol["protocol_id"],
                detected_deviations,
                visit_records,
                protocol["visit_schedule"],
            )
            assert isinstance(score["risk_score"], int)

    def test_risk_score_contract_fields_present(self, risk_ranking):
        required = {
            "site_id", "protocol_id", "risk_score", "risk_band",
            "computed_at", "indicator_breakdown", "trend",
            "open_deviation_count", "total_visits",
        }
        for score in risk_ranking:
            assert required <= set(score.keys()), f"missing fields on {score['site_id']}"

    def test_risk_score_in_valid_range(self, risk_ranking):
        for score in risk_ranking:
            assert 0 <= score["risk_score"] <= 100, (
                f"{score['site_id']} risk_score {score['risk_score']} out of [0, 100]"
            )

    def test_risk_band_is_valid_value(self, risk_ranking):
        valid_bands = {"High", "Medium", "Low"}
        for score in risk_ranking:
            assert score["risk_band"] in valid_bands

    def test_trend_is_valid_value(self, risk_ranking):
        valid_trends = {"worsening", "improving", "stable", "volatile"}
        for score in risk_ranking:
            assert score["trend"] in valid_trends, (
                f"{score['site_id']} has unexpected trend: {score['trend']!r}"
            )

    def test_indicator_breakdown_sums_to_one_or_zero(self, risk_ranking):
        # Each of the 5 indicators is rounded to 4 decimal places independently,
        # so their sum can deviate from 1.0 by up to 5 × 0.00005 = 0.00025.
        # Tolerance of 1e-3 comfortably covers that rounding budget.
        for score in risk_ranking:
            total = sum(score["indicator_breakdown"].values())
            assert abs(total - 1.0) < 1e-3 or total == 0.0, (
                f"{score['site_id']} indicator_breakdown sums to {total}"
            )

    def test_open_deviation_count_matches_detected_deviations(
        self, detected_deviations, risk_ranking
    ):
        """open_deviation_count in every RiskScore must equal the number of
        Deviations Track A actually found for that site."""
        detected_per_site = {}
        for d in detected_deviations:
            detected_per_site[d["site_id"]] = detected_per_site.get(d["site_id"], 0) + 1

        for score in risk_ranking:
            expected = detected_per_site.get(score["site_id"], 0)
            assert score["open_deviation_count"] == expected, (
                f"{score['site_id']}: B reports {score['open_deviation_count']} "
                f"open deviations but A found {expected}"
            )

    def test_seeded_high_risk_sites_rank_above_low_risk_sites(self, sites, risk_ranking):
        """The seeded high-tier sites must, on average, score higher than
        seeded low-tier sites — the core sanity check for the whole pipeline."""
        tier = {s["site_id"]: s["seed_risk_tier"] for s in sites}
        score_by_site = {r["site_id"]: r["risk_score"] for r in risk_ranking}

        high_scores = [score_by_site[sid] for sid, t in tier.items() if t == "high"]
        low_scores = [score_by_site[sid] for sid, t in tier.items() if t == "low"]

        avg_high = sum(high_scores) / len(high_scores)
        avg_low = sum(low_scores) / len(low_scores)

        assert avg_high > avg_low, (
            f"avg high-tier score ({avg_high:.1f}) not above avg low-tier ({avg_low:.1f})"
        )

    def test_zero_deviation_sites_score_zero(self, deviations_by_site, risk_ranking):
        """Sites Track A found no deviations for must score exactly 0."""
        sites_with_deviations = set(deviations_by_site.keys())
        for score in risk_ranking:
            if score["site_id"] not in sites_with_deviations:
                assert score["risk_score"] == 0, (
                    f"{score['site_id']} has no deviations but risk_score={score['risk_score']}"
                )

    def test_ranking_is_sorted_descending(self, risk_ranking):
        scores = [r["risk_score"] for r in risk_ranking]
        assert scores == sorted(scores, reverse=True)

    def test_every_site_appears_exactly_once_in_ranking(self, site_ids, risk_ranking):
        ranked_ids = [r["site_id"] for r in risk_ranking]
        assert sorted(ranked_ids) == sorted(site_ids)


# ---------------------------------------------------------------------------
# A → C: Deviation contract → CAPA Generation
# ---------------------------------------------------------------------------


class TestTrackAToTrackC:
    def test_track_a_output_feeds_track_c_without_error(
        self, protocol, ich_corpus, detected_deviations
    ):
        """Track C must accept Track A's raw deviation dicts and generate a
        complete report without any transformation in between."""
        dev = detected_deviations[0]
        report = generator.generate(
            "deviation", [dev], protocol, ich_corpus, "CAPA-INT-A2C-001"
        )
        assert isinstance(report, CapaReport)

    def test_capa_report_contract_fields_present(
        self, protocol, ich_corpus, detected_deviations
    ):
        required = {
            "capa_id", "scope", "site_id", "related_deviation_ids",
            "root_cause", "corrective_action", "preventive_action",
            "suggested_owner_role", "suggested_due_window_days",
            "generated_at", "evidence_citations",
        }
        report = generator.generate(
            "deviation", [detected_deviations[0]], protocol, ich_corpus, "CAPA-INT-FIELDS"
        )
        assert set(report.to_dict().keys()) == required

    def test_no_hallucination_end_to_end(
        self, protocol, ich_corpus, detected_deviations, deviations_by_site
    ):
        """The no-hallucination guarantee must hold when citations are built
        from Track A's real output — every citation traces to a real
        deviation_id A produced, a real protocol section, or a real ICH chunk."""
        valid_deviation_ids = {d["deviation_id"] for d in detected_deviations}
        valid_clauses = {
            f"Section {s['section_id']} - {s['title']}"
            for s in protocol["protocol_sections"]
        }
        valid_ich = {corpus.ich_citation_string(c) for c in ich_corpus.values()}

        # Sample: first 10 deviation-scope + first 5 site-scope reports
        reports = []
        for dev in detected_deviations[:10]:
            reports.append(
                generator.generate(
                    "deviation", [dev], protocol, ich_corpus,
                    f"CAPA-INT-HAL-{dev['deviation_id']}"
                )
            )
        for site_id, devs in list(deviations_by_site.items())[:5]:
            reports.append(
                generator.generate(
                    "site", devs, protocol, ich_corpus,
                    f"CAPA-INT-HAL-{site_id}"
                )
            )

        for report in reports:
            for citation in report.evidence_citations:
                assert (
                    citation in valid_deviation_ids
                    or citation in valid_clauses
                    or citation in valid_ich
                ), (
                    f"unverifiable citation on {report.capa_id}: {citation!r} — "
                    "not in Track A deviation ids, protocol clauses, or ICH corpus"
                )

    def test_protocol_clause_refs_from_track_a_are_valid_for_track_c(
        self, protocol, detected_deviations
    ):
        """Every protocol_clause_ref on a Track A deviation must be a string
        that exists in the protocol's own sections list — so Track C can cite
        it without fabricating a section."""
        valid_clauses = {
            f"Section {s['section_id']} - {s['title']}"
            for s in protocol["protocol_sections"]
        }
        for dev in detected_deviations:
            ref = dev.get("protocol_clause_ref", "")
            if ref:  # non-empty refs must be valid
                assert ref in valid_clauses, (
                    f"Track A emitted unverifiable clause ref: {ref!r} "
                    f"on deviation {dev['deviation_id']}"
                )

    def test_capa_deviation_ids_are_subset_of_track_a_output(
        self, protocol, ich_corpus, detected_deviations
    ):
        """Every deviation_id cited in a CapaReport's related_deviation_ids
        must be an id Track A actually produced."""
        valid_ids = {d["deviation_id"] for d in detected_deviations}
        for dev in detected_deviations[:15]:
            report = generator.generate(
                "deviation", [dev], protocol, ich_corpus,
                f"CAPA-INT-IDS-{dev['deviation_id']}"
            )
            for rid in report.related_deviation_ids:
                assert rid in valid_ids, (
                    f"{report.capa_id} cites deviation {rid!r} not in Track A output"
                )

    def test_track_a_deviation_types_all_have_capa_templates(
        self, protocol, ich_corpus, detected_deviations
    ):
        """Every deviation type Track A emits must have a CAPA template —
        no UnknownType error can surface in production."""
        types_seen = {d["type"] for d in detected_deviations}
        for dev in detected_deviations:
            if dev["type"] in types_seen:
                # just need one representative per type
                generator.generate(
                    "deviation", [dev], protocol, ich_corpus,
                    f"CAPA-INT-TYPE-{dev['deviation_id']}"
                )
                types_seen.discard(dev["type"])
            if not types_seen:
                break


# ---------------------------------------------------------------------------
# B → C: Risk score context → CAPA ownership/urgency alignment
# ---------------------------------------------------------------------------


class TestTrackBToTrackC:
    def test_highest_risk_site_capa_has_shortest_due_window(
        self, protocol, ich_corpus, detected_deviations, risk_ranking, deviations_by_site
    ):
        """The top-ranked site from B must have at least one deviation — and
        the resulting CAPA's due window must be ≤14 days (Major or Minor
        severity), reflecting the urgency Track B's ranking implies."""
        top_site = risk_ranking[0]["site_id"]
        devs = deviations_by_site.get(top_site)
        assert devs, f"top-ranked site {top_site} has no deviations in Track A output"

        report = generator.generate(
            "site", devs, protocol, ich_corpus, f"CAPA-INT-TOP-{top_site}"
        )
        assert report.suggested_due_window_days <= 14, (
            f"top-risk site {top_site} got a {report.suggested_due_window_days}-day "
            "window — expected ≤14 given the severity of its deviations"
        )

    def test_severity_from_track_a_drives_owner_in_track_c(
        self, protocol, ich_corpus, detected_deviations
    ):
        """For every individual deviation CAPA, the suggested_owner_role must
        match the owner the severity policy maps Track A's severity to."""
        for dev in detected_deviations[:20]:
            report = generator.generate(
                "deviation", [dev], protocol, ich_corpus,
                f"CAPA-INT-OWN-{dev['deviation_id']}"
            )
            expected_owner = OWNER_ROLE_BY_SEVERITY[dev["severity"]]
            assert report.suggested_owner_role == expected_owner, (
                f"{report.capa_id}: severity={dev['severity']!r} → "
                f"expected owner {expected_owner!r}, got {report.suggested_owner_role!r}"
            )

    def test_severity_from_track_a_drives_due_window_in_track_c(
        self, protocol, ich_corpus, detected_deviations
    ):
        """For every individual deviation CAPA, the suggested_due_window_days
        must match the due window the severity policy maps Track A's severity to."""
        for dev in detected_deviations[:20]:
            report = generator.generate(
                "deviation", [dev], protocol, ich_corpus,
                f"CAPA-INT-DUE-{dev['deviation_id']}"
            )
            expected_days = DUE_WINDOW_DAYS_BY_SEVERITY[dev["severity"]]
            assert report.suggested_due_window_days == expected_days, (
                f"{report.capa_id}: severity={dev['severity']!r} → "
                f"expected {expected_days} days, got {report.suggested_due_window_days}"
            )


# ---------------------------------------------------------------------------
# Full A → B → C pipeline: every site, no exceptions
# ---------------------------------------------------------------------------


class TestFullPipelineABC:
    def test_full_pipeline_runs_on_every_site_without_raising(
        self, protocol, visit_records, ich_corpus, detected_deviations,
        deviations_by_site, site_ids
    ):
        """The complete A→B→C pipeline must not raise for any site in the
        synthetic dataset — the most important single integration guarantee."""
        for site_id in site_ids:
            # B: score this site using A's output
            score = compute_site_risk_score(
                site_id,
                protocol["protocol_id"],
                detected_deviations,
                visit_records,
                protocol["visit_schedule"],
            )
            assert score is not None

            # C: generate a CAPA only if A found deviations (expected for most sites)
            devs = deviations_by_site.get(site_id)
            if devs:
                report = generator.generate(
                    "site", devs, protocol, ich_corpus,
                    f"CAPA-PIPELINE-{site_id}"
                )
                assert report.root_cause.strip()
                assert report.corrective_action.strip()
                assert report.preventive_action.strip()
                assert report.evidence_citations  # must be non-empty

    def test_deviation_types_emitted_by_track_a_are_valid_contract_types(
        self, detected_deviations
    ):
        """Every deviation type Track A emits must be in the shared contract
        set (docs/04_data_schema.md DEVIATION_TYPES)."""
        for dev in detected_deviations:
            assert dev["type"] in DEVIATION_TYPES, (
                f"Track A emitted unknown type {dev['type']!r} "
                f"on deviation {dev['deviation_id']}"
            )

    def test_severities_emitted_by_track_a_are_valid_contract_values(
        self, detected_deviations
    ):
        for dev in detected_deviations:
            assert dev["severity"] in SEVERITIES, (
                f"Track A emitted unknown severity {dev['severity']!r} "
                f"on deviation {dev['deviation_id']}"
            )

    def test_all_track_a_deviations_have_non_empty_narrative_fields(
        self, detected_deviations
    ):
        for dev in detected_deviations:
            assert dev["deviation_id"].startswith("DEV-")
            assert dev["severity_rationale"].strip(), (
                f"{dev['deviation_id']} has empty severity_rationale"
            )
            assert dev["protocol_clause_ref"].strip(), (
                f"{dev['deviation_id']} has empty protocol_clause_ref"
            )

    def test_track_b_total_visits_matches_visit_records(
        self, visit_records, risk_ranking
    ):
        """total_visits on each RiskScore must equal the number of visit
        records Track C's generator actually produced for that site."""
        visits_per_site = {}
        for v in visit_records:
            visits_per_site[v["site_id"]] = visits_per_site.get(v["site_id"], 0) + 1

        for score in risk_ranking:
            expected = visits_per_site.get(score["site_id"], 0)
            assert score["total_visits"] == expected, (
                f"{score['site_id']}: B reports {score['total_visits']} total visits "
                f"but visit_records has {expected}"
            )

    def test_capa_site_id_matches_deviation_site_ids(
        self, protocol, ich_corpus, deviations_by_site
    ):
        """site_id on the generated CapaReport must match the site_id on
        every input deviation — no cross-site contamination anywhere in the
        pipeline."""
        for site_id, devs in list(deviations_by_site.items())[:8]:
            report = generator.generate(
                "site", devs, protocol, ich_corpus,
                f"CAPA-PIPE-SITE-{site_id}"
            )
            assert report.site_id == site_id
            for dev in devs:
                assert dev["site_id"] == site_id

    def test_pipeline_deviation_count_is_consistent_across_tracks(
        self, detected_deviations, risk_ranking, deviations_by_site
    ):
        """Total deviations Track A found must equal the sum of
        open_deviation_count across all RiskScores (Track B), and also equal
        the total deviations available to Track C."""
        total_from_a = len(detected_deviations)
        total_from_b = sum(r["open_deviation_count"] for r in risk_ranking)
        total_from_c = sum(len(devs) for devs in deviations_by_site.values())

        assert total_from_a == total_from_b, (
            f"Track A found {total_from_a} deviations; "
            f"Track B counts {total_from_b} across all sites"
        )
        assert total_from_a == total_from_c, (
            f"Track A found {total_from_a} deviations; "
            f"Track C sees {total_from_c} across all sites"
        )
