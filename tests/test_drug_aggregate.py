"""Track B stretch-feature test cases for the drug-level aggregation
(`src/risk_scoring/drug_aggregate.py`): a clearly approval-ready drug, a
clearly at-risk drug, the CAPA-data-unavailable redistribution behavior,
and the zero-sites edge case.

Fixtures are hand-built RiskScore/Deviation-shaped dicts (not the
generated data/synthetic dataset) so the expected numbers are exactly
derivable, matching tests/test_risk_scoring.py's convention.
"""

import pytest

from src.risk_scoring.drug_aggregate import compute_drug_performance

PROTOCOL_ID = "TEST-PROTO"


def _site_score(site_id: str, risk_score: int, risk_band: str, trend: str = "stable", total_visits: int = 100) -> dict:
    return {
        "site_id": site_id,
        "protocol_id": PROTOCOL_ID,
        "risk_score": risk_score,
        "risk_band": risk_band,
        "trend": trend,
        "open_deviation_count": 0,
        "total_visits": total_visits,
    }


def _deviation(severity: str) -> dict:
    return {"severity": severity}


def test_clearly_approval_ready_drug():
    """10 clean/low sites, no Major deviations, no CAPA reports outstanding
    (none needed) -- should land well under the Conditional threshold."""
    ranking = [_site_score(f"SITE-{i}", risk_score=5 + i, risk_band="Low", total_visits=100) for i in range(10)]
    deviations = [_deviation("Administrative") for _ in range(5)] + [_deviation("Minor") for _ in range(3)]

    result = compute_drug_performance(PROTOCOL_ID, ranking, deviations, capa_reports=[])

    assert result["readiness_band"] == "Likely Approval Ready"
    assert result["drug_risk_index"] < 25
    assert result["sites_by_band"] == {"High": 0, "Medium": 0, "Low": 10}
    assert result["capa_summary"] == {"total": 0, "approved": 0, "pending_review": 0, "rejected": 0}
    assert sum(result["factor_breakdown"].values()) == pytest.approx(1.0)


def test_clearly_high_risk_drug():
    """Most sites High-band, a high Major-deviation rate, and CAPA reports
    that are mostly pending/rejected -- should cross into High Risk of
    Rejection given every factor is saturated in the same direction."""
    ranking = (
        [_site_score(f"SITE-HIGH-{i}", risk_score=95, risk_band="High", trend="worsening", total_visits=50) for i in range(6)]
        + [_site_score(f"SITE-MED-{i}", risk_score=50, risk_band="Medium", total_visits=50) for i in range(2)]
    )
    # 30 Major deviations across 400 total visits -> rate 0.075, far above
    # drug_aggregate.MAJOR_DEVIATION_RATE_CAP (0.015), so this factor saturates.
    deviations = [_deviation("Major") for _ in range(30)] + [_deviation("Minor") for _ in range(5)]
    capa_reports = (
        [{"capa_id": f"CAPA-{i}", "site_id": f"SITE-HIGH-{i}", "review_status": "rejected"} for i in range(4)]
        + [{"capa_id": "CAPA-P1", "site_id": "SITE-HIGH-4", "review_status": "pending_review"}]
        + [{"capa_id": "CAPA-A1", "site_id": "SITE-HIGH-5", "review_status": "approved"}]
    )

    result = compute_drug_performance(PROTOCOL_ID, ranking, deviations, capa_reports=capa_reports)

    assert result["readiness_band"] == "High Risk of Rejection"
    assert result["drug_risk_index"] >= 55
    assert result["sites_by_band"]["High"] == 6
    assert result["capa_summary"] == {"total": 6, "approved": 1, "pending_review": 1, "rejected": 4}


def test_missing_capa_data_is_not_treated_as_zero_risk():
    """A caller with no CAPA visibility (capa_reports=None, e.g. Track B's
    standalone service) must not silently score as if every issue were
    already resolved -- the factor should drop out and its weight
    redistribute, not collapse to 'best case'. With identical site/deviation
    data, the None case's index should be >= the explicit-empty-list case
    (which asserts zero CAPAs are actually needed)."""
    ranking = [_site_score("SITE-A", risk_score=60, risk_band="Medium", total_visits=80)]
    deviations = [_deviation("Major") for _ in range(2)]

    with_explicit_none_needed = compute_drug_performance(PROTOCOL_ID, ranking, deviations, capa_reports=[])
    without_capa_visibility = compute_drug_performance(PROTOCOL_ID, ranking, deviations, capa_reports=None)

    assert without_capa_visibility["capa_summary"] is None
    assert with_explicit_none_needed["capa_summary"] is not None
    assert without_capa_visibility["drug_risk_index"] >= with_explicit_none_needed["drug_risk_index"]
    assert sum(without_capa_visibility["factor_breakdown"].values()) == pytest.approx(1.0)
    assert "unresolved_capa_rate" not in without_capa_visibility["factor_breakdown"]


def test_zero_sites_raises():
    with pytest.raises(ValueError):
        compute_drug_performance(PROTOCOL_ID, [], [], capa_reports=None)


def test_rationale_cites_real_numbers_not_hallucinated():
    """Every rationale line is generated from the same aggregated counts
    returned alongside it -- never a free-text/LLM sentence -- so the
    Major-deviation count it cites must match deviations_by_severity."""
    ranking = [_site_score("SITE-A", risk_score=80, risk_band="High", total_visits=50)]
    deviations = [_deviation("Major") for _ in range(3)]

    result = compute_drug_performance(PROTOCOL_ID, ranking, deviations, capa_reports=None)

    major_count = result["deviations_by_severity"]["Major"]
    assert any(str(major_count) in line for line in result["rationale"])
