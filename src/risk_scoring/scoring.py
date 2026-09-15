"""Weighted site risk scoring model — Track B.

Implements the model documented in DESIGN.md: five raw indicators, each
weighted, rolled up into a 0-100 risk_score plus an indicator_breakdown
whose shares sum to 1.0. Output matches the Site Risk Score object in
docs/04_data_schema.md section 4.

CLI usage (sanity check against the real synthetic dataset):
    python -m src.risk_scoring.scoring --data-dir data/synthetic
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path

from . import indicators
from .loaders import load_deviations, load_protocol, load_sites, load_visit_records
from .trend import classify_trend

# Order matches the worked example in docs/04_data_schema.md section 4.
WEIGHTS = {
    "severity_mix_weight": 0.35,
    "deviation_frequency": 0.25,
    "repeat_offense_rate": 0.20,
    "recency_weight": 0.10,
    "trend_slope": 0.10,
}

RISK_BAND_HIGH = 70
RISK_BAND_MEDIUM = 40

def compute_site_risk_score(
    site_id: str,
    protocol_id: str,
    all_deviations: list[dict],
    all_visit_records: list[dict],
    visit_schedule: list[dict],
    as_of: date | None = None,
) -> dict:
    """Compute the RiskScore object for one site.

    `all_deviations` / `all_visit_records` are the full dataset; this
    function filters to the given site itself so callers don't have to.
    """
    site_deviations = [d for d in all_deviations if d["site_id"] == site_id]
    site_visits = [v for v in all_visit_records if v["site_id"] == site_id]
    total_visits = len(site_visits)

    if as_of is None:
        visit_dates = [v.get("actual_date") or v.get("scheduled_date") for v in site_visits]
        parsed = [datetime.fromisoformat(d).date() for d in visit_dates if d]
        as_of = max(parsed) if parsed else date.today()

    if site_deviations:
        _, trend_scored_raw = indicators.trend_slope(site_deviations, site_visits, visit_schedule)
        raw = {
            "severity_mix_weight": indicators.severity_mix_weight(site_deviations, total_visits),
            "deviation_frequency": indicators.deviation_frequency(site_deviations, total_visits),
            "repeat_offense_rate": indicators.repeat_offense_rate(site_deviations),
            "recency_weight": indicators.recency_weight(site_deviations, total_visits, as_of),
            "trend_slope": trend_scored_raw,
        }
    else:
        # No deviations at all: there is no risk signal and no trend to
        # speak of — a neutral (0.5) trend_slope would otherwise still
        # contribute points. See DESIGN.md's zero-deviation edge case.
        raw = {k: 0.0 for k in WEIGHTS}

    contributions = {k: WEIGHTS[k] * raw[k] for k in WEIGHTS}
    contribution_sum = sum(contributions.values())

    risk_score = round(100 * contribution_sum)
    if contribution_sum > 0:
        indicator_breakdown = {k: round(v / contribution_sum, 4) for k, v in contributions.items()}
    else:
        indicator_breakdown = {k: 0.0 for k in WEIGHTS}

    if risk_score >= RISK_BAND_HIGH:
        risk_band = "High"
    elif risk_score >= RISK_BAND_MEDIUM:
        risk_band = "Medium"
    else:
        risk_band = "Low"

    return {
        "site_id": site_id,
        "protocol_id": protocol_id,
        "risk_score": risk_score,
        "risk_band": risk_band,
        "computed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "indicator_breakdown": indicator_breakdown,
        "trend": classify_trend(site_deviations, site_visits, visit_schedule),
        "open_deviation_count": len(site_deviations),
        "total_visits": total_visits,
    }


def rank_sites(
    protocol_id: str,
    all_deviations: list[dict],
    all_visit_records: list[dict],
    visit_schedule: list[dict],
    site_ids: list[str],
    as_of: date | None = None,
) -> list[dict]:
    """RiskScore objects for every site, ranked by risk_score descending."""
    scores = [
        compute_site_risk_score(
            site_id, protocol_id, all_deviations, all_visit_records, visit_schedule, as_of
        )
        for site_id in site_ids
    ]
    return sorted(scores, key=lambda s: s["risk_score"], reverse=True)


def _main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/synthetic"))
    args = parser.parse_args()

    protocol = load_protocol(args.data_dir)
    sites = load_sites(args.data_dir)
    visit_records = load_visit_records(args.data_dir)
    deviations = load_deviations(args.data_dir)

    ranking = rank_sites(
        protocol["protocol_id"],
        deviations,
        visit_records,
        protocol["visit_schedule"],
        [s["site_id"] for s in sites],
    )

    seed_tier_by_site = {s["site_id"]: s["seed_risk_tier"] for s in sites}
    print(f"{'site_id':10} {'score':>5} {'band':8} {'trend':10} {'open_dev':>8} {'visits':>6}  seed_tier")
    for r in ranking:
        print(
            f"{r['site_id']:10} {r['risk_score']:>5} {r['risk_band']:8} {r['trend']:10} "
            f"{r['open_deviation_count']:>8} {r['total_visits']:>6}  {seed_tier_by_site[r['site_id']]}"
        )

    print("\nTop-ranked site detail:")
    print(json.dumps(ranking[0], indent=2))


if __name__ == "__main__":
    _main()
