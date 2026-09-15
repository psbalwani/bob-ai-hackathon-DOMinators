"""Track B test cases, per docs/03_team_division.md Task 6:
a clearly high-risk site, a clearly low-risk site, and the edge case
(few visits, one Major deviation) that sanity-checks the score isn't
gameable by volume alone.

Fixtures are hand-built (not the generated data/synthetic dataset) so the
expected numbers are exactly derivable and the tests don't depend on
regenerating data with a particular seed.
"""

from datetime import date, timedelta

from src.risk_scoring.scoring import compute_site_risk_score

PROTOCOL_ID = "TEST-PROTO"
EPOCH = date(2026, 1, 1)

# A 4-visit protocol spanning 90 days, used by every test in this file.
SCHEDULE = [
    {"visit_id": "V1", "scheduled_day": 0},
    {"visit_id": "V2", "scheduled_day": 30},
    {"visit_id": "V3", "scheduled_day": 60},
    {"visit_id": "V4", "scheduled_day": 90},
]
DAY_BY_VISIT_ID = {v["visit_id"]: v["scheduled_day"] for v in SCHEDULE}


def _iso(day: int) -> str:
    return (EPOCH + timedelta(days=day)).isoformat()


def _visit(record_id: str, patient_id: str, site_id: str, visit_id: str) -> dict:
    d = _iso(DAY_BY_VISIT_ID[visit_id])
    return {
        "visit_record_id": record_id,
        "patient_id": patient_id,
        "site_id": site_id,
        "protocol_id": PROTOCOL_ID,
        "visit_id": visit_id,
        "scheduled_date": d,
        "actual_date": d,
        "dosage_administered_mg": None,
        "comedications": [],
        "procedures_completed": [],
    }


def _deviation(
    dev_id: str, visit_record_id: str, patient_id: str, site_id: str, severity: str, visit_id: str
) -> dict:
    # detected_at mirrors the visit's own date, matching loaders.py's mock adapter.
    visit_day = DAY_BY_VISIT_ID[visit_id]
    return {
        "deviation_id": dev_id,
        "visit_record_id": visit_record_id,
        "patient_id": patient_id,
        "site_id": site_id,
        "protocol_id": PROTOCOL_ID,
        "type": "other",
        "severity": severity,
        "severity_rationale": "test fixture",
        "protocol_clause_ref": "",
        "detected_at": f"{_iso(visit_day)}T00:00:00Z",
        "detector_version": "test",
    }


def _patient_visits(site_id: str, patient_id: str) -> list[dict]:
    """One visit record per visit_id in SCHEDULE, record_id encodes the visit_id."""
    return [_visit(f"{patient_id}-{v['visit_id']}", patient_id, site_id, v["visit_id"]) for v in SCHEDULE]


def test_clearly_high_risk_site():
    """5 patients, 3 of whom have Major deviations at both their late visits
    (V3, V4) -- severe, frequent, recent, repeat-offending, and worsening.
    Every indicator saturates its cap, so this is a deterministic max score.
    """
    site_id = "SITE-HIGH"
    patients = [f"PT-{i}" for i in range(1, 6)]
    visits = [v for p in patients for v in _patient_visits(site_id, p)]

    deviations = []
    for p in patients[:3]:  # PT-1, PT-2, PT-3: repeat offenders
        deviations.append(_deviation(f"{p}-DEV-V3", f"{p}-V3", p, site_id, "Major", "V3"))
        deviations.append(_deviation(f"{p}-DEV-V4", f"{p}-V4", p, site_id, "Major", "V4"))

    result = compute_site_risk_score(site_id, PROTOCOL_ID, deviations, visits, SCHEDULE)

    assert result["open_deviation_count"] == 6
    assert result["total_visits"] == 20
    assert result["risk_score"] == 100
    assert result["risk_band"] == "High"
    assert result["trend"] == "worsening"
    # Every indicator should be maxed out (contribution = weight) given the
    # extreme, clustered construction above.
    assert result["indicator_breakdown"]["severity_mix_weight"] > 0
    assert sum(result["indicator_breakdown"].values()) == 1.0


def test_clearly_low_risk_site():
    """13 patients (52 visits), 2 unrelated Administrative deviations from
    different patients at different, non-adjacent-in-time visits -- no
    repeat offenders, low severity, and (for one of them) already aged out
    of the recency window.
    """
    site_id = "SITE-LOW"
    patients = [f"PT-{i}" for i in range(1, 14)]
    visits = [v for p in patients for v in _patient_visits(site_id, p)]

    deviations = [
        _deviation("DEV-1", "PT-1-V1", "PT-1", site_id, "Administrative", "V1"),
        _deviation("DEV-2", "PT-2-V2", "PT-2", site_id, "Administrative", "V2"),
    ]

    result = compute_site_risk_score(site_id, PROTOCOL_ID, deviations, visits, SCHEDULE)

    assert result["open_deviation_count"] == 2
    assert result["total_visits"] == 52
    assert result["risk_score"] < 40
    assert result["risk_band"] == "Low"
    # No patient has more than one deviation.
    assert result["indicator_breakdown"]["repeat_offense_rate"] == 0.0


def test_zero_deviations_is_low_not_gamed_the_other_way():
    """A site with no deviations at all must score exactly 0, not some
    neutral baseline (see DESIGN.md's zero-deviation edge case)."""
    site_id = "SITE-CLEAN"
    visits = _patient_visits(site_id, "PT-1")

    result = compute_site_risk_score(site_id, PROTOCOL_ID, [], visits, SCHEDULE)

    assert result["risk_score"] == 0
    assert result["risk_band"] == "Low"
    assert all(v == 0.0 for v in result["indicator_breakdown"].values())


def test_one_major_deviation_is_not_gameable_by_visit_volume():
    """The edge case from docs/03_team_division.md: a tiny site with a
    single Major deviation must be flagged, and a large site can't hide an
    identical single Major deviation just by having many more visits --
    both sites have open_deviation_count == 1, but risk_score must differ
    sharply because the model rate-normalizes rather than counting raw
    deviations.
    """
    tiny_site = "SITE-TINY"
    tiny_visits = _patient_visits(tiny_site, "PT-1")[:2]  # only V1, V2 -> 2 total visits
    tiny_deviations = [_deviation("DEV-TINY", "PT-1-V1", "PT-1", tiny_site, "Major", "V1")]

    tiny_result = compute_site_risk_score(tiny_site, PROTOCOL_ID, tiny_deviations, tiny_visits, SCHEDULE)

    bulky_site = "SITE-BULKY"
    bulky_patients = [f"PT-{i}" for i in range(1, 51)]  # 50 patients x 4 visits = 200 visits
    bulky_visits = [v for p in bulky_patients for v in _patient_visits(bulky_site, p)]
    bulky_deviations = [_deviation("DEV-BULKY", "PT-1-V1", "PT-1", bulky_site, "Major", "V1")]

    bulky_result = compute_site_risk_score(bulky_site, PROTOCOL_ID, bulky_deviations, bulky_visits, SCHEDULE)

    # Same raw deviation count on both sides -- the score must not be equal.
    assert tiny_result["open_deviation_count"] == bulky_result["open_deviation_count"] == 1
    assert tiny_result["total_visits"] == 2
    assert bulky_result["total_visits"] == 200

    assert tiny_result["risk_score"] > bulky_result["risk_score"]
    # A single Major deviation among only 2 visits is a real signal.
    assert tiny_result["risk_score"] >= 70
    assert tiny_result["risk_band"] == "High"
    # The same single deviation, diluted across 200 visits, stays quiet.
    assert bulky_result["risk_band"] == "Low"
