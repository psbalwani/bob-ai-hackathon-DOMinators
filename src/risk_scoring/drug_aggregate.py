"""Drug-level performance aggregation — Track B stretch feature.

Rolls up every site's `RiskScore` (scoring.py) plus the drug's deviations
and CAPA remediation status into a single `DrugPerformance` object: one
number + one verdict a trial sponsor/regulatory-affairs lead can read as
"is this drug's site network in a state that would pass an FDA inspection
right now." This does NOT re-score sites — it aggregates the outputs
Track B/A/C already produce, the same way `pipeline.dashboard_summary`
aggregates `rank_sites` output for the Trial Overview screen. See
DESIGN.md's "Drug-Level Aggregation" section for the full rationale.

Matches the `Drug Performance Summary` object in `docs/04_data_schema.md`
section 7 and `GET /dashboard/drug-performance` in `docs/05_api_contracts.md`.

CLI usage (sanity check against the real synthetic dataset):
    python -m src.risk_scoring.drug_aggregate --data-dir data/synthetic
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from .loaders import load_deviations, load_protocol, load_sites, load_visit_records
from .scoring import rank_sites

# Weight of each factor when CAPA remediation data is available. Mirrors
# scoring.py's WEIGHTS in spirit (documented, sums to 1.0) but at the
# drug/portfolio level rather than the single-site level.
WEIGHTS = {
    "avg_site_risk": 0.35,
    "high_risk_site_share": 0.25,
    "major_deviation_rate": 0.20,
    "unresolved_capa_rate": 0.10,
    "trend_pressure": 0.10,
}

# Track B's own standalone service (api.py) has no CAPA data (that's Track
# C/D's domain) -- when capa_reports is None, drop that factor and
# renormalize the rest proportionally rather than silently treating "no
# data" as "0 unresolved CAPAs" (which would understate risk).
_WEIGHTS_NO_CAPA = {k: w / (1 - WEIGHTS["unresolved_capa_rate"]) for k, w in WEIGHTS.items() if k != "unresolved_capa_rate"}

# Calibrated the same way as indicators.py's caps: measured against the
# real 10-drug portfolio (data/synthetic/ + data/synthetic/drugs/*) rather
# than picked abstractly, so the worst real drug lands near saturation
# instead of pegging every drug at 1.0. See DESIGN.md.
MAJOR_DEVIATION_RATE_CAP = 0.015

READINESS_HIGH_RISK = 55
READINESS_CONDITIONAL = 25

FACTOR_LABELS = {
    "avg_site_risk": "Average site risk score",
    "high_risk_site_share": "Share of sites in the High risk band",
    "major_deviation_rate": "Major (patient-safety) deviation rate",
    "unresolved_capa_rate": "Unresolved CAPA reports",
    "trend_pressure": "Sites trending worse vs. better",
}


def compute_drug_performance(
    protocol_id: str,
    ranking: list[dict],
    deviations: list[dict],
    capa_reports: list[dict] | None = None,
) -> dict:
    """Aggregate one drug's site-level results into a `DrugPerformance` object.

    `ranking` is the output of `scoring.rank_sites` (or persisted
    equivalents) for every site under this protocol. `deviations` is every
    `Deviation` for this protocol. `capa_reports` is a list of
    `{"site_id", "review_status"}` (or richer CAPA dicts -- only those two
    keys are read); pass `None` when CAPA data isn't available to this
    caller (e.g. Track B's standalone service) rather than `[]`, which
    would be read as "zero CAPAs needed."
    """
    total_sites = len(ranking)
    if total_sites == 0:
        raise ValueError("cannot aggregate drug performance with zero sites")

    sites_by_band = {"High": 0, "Medium": 0, "Low": 0}
    trend_breakdown = {"worsening": 0, "improving": 0, "stable": 0, "volatile": 0}
    for s in ranking:
        sites_by_band[s["risk_band"]] += 1
        trend_breakdown[s["trend"]] += 1

    total_visits_drug = sum(s["total_visits"] for s in ranking)
    deviations_by_severity = {"Major": 0, "Minor": 0, "Administrative": 0}
    for d in deviations:
        deviations_by_severity[d["severity"]] += 1

    # --- raw indicators, each normalized to [0, 1], higher = worse -------
    avg_site_risk_raw = sum(s["risk_score"] for s in ranking) / total_sites / 100
    high_risk_site_share_raw = sites_by_band["High"] / total_sites
    major_rate = deviations_by_severity["Major"] / total_visits_drug if total_visits_drug else 0.0
    major_deviation_rate_raw = min(major_rate / MAJOR_DEVIATION_RATE_CAP, 1.0)
    trend_pressure_raw = (trend_breakdown["worsening"] + 0.5 * trend_breakdown["volatile"]) / total_sites

    raw = {
        "avg_site_risk": avg_site_risk_raw,
        "high_risk_site_share": high_risk_site_share_raw,
        "major_deviation_rate": major_deviation_rate_raw,
        "trend_pressure": trend_pressure_raw,
    }

    capa_summary = None
    weights = _WEIGHTS_NO_CAPA
    if capa_reports is not None:
        total_capas = len(capa_reports)
        approved = sum(1 for c in capa_reports if c["review_status"] == "approved")
        pending = sum(1 for c in capa_reports if c["review_status"] == "pending_review")
        rejected = sum(1 for c in capa_reports if c["review_status"] == "rejected")
        capa_summary = {"total": total_capas, "approved": approved, "pending_review": pending, "rejected": rejected}
        # Rejected remediation is worse than merely awaiting review; approved
        # contributes nothing (the issue is considered addressed).
        unresolved_raw = (pending * 0.6 + rejected * 1.0) / total_capas if total_capas else 0.0
        raw["unresolved_capa_rate"] = unresolved_raw
        weights = WEIGHTS

    contributions = {k: weights[k] * raw[k] for k in weights}
    contribution_sum = sum(contributions.values())
    drug_risk_index = round(100 * contribution_sum)
    if contribution_sum > 0:
        factor_breakdown = {k: round(v / contribution_sum, 4) for k, v in contributions.items()}
    else:
        factor_breakdown = {k: 0.0 for k in weights}

    if drug_risk_index >= READINESS_HIGH_RISK:
        readiness_band = "High Risk of Rejection"
    elif drug_risk_index >= READINESS_CONDITIONAL:
        readiness_band = "Conditional — Remediation Required"
    else:
        readiness_band = "Likely Approval Ready"

    top_risk_sites = [
        {"site_id": s["site_id"], "risk_score": s["risk_score"], "risk_band": s["risk_band"]}
        for s in sorted(ranking, key=lambda s: s["risk_score"], reverse=True)[:5]
    ]

    return {
        "protocol_id": protocol_id,
        "computed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "drug_risk_index": drug_risk_index,
        "readiness_band": readiness_band,
        "factor_breakdown": factor_breakdown,
        "rationale": _build_rationale(factor_breakdown, raw, sites_by_band, deviations_by_severity, capa_summary, total_sites),
        "total_sites": total_sites,
        "sites_by_band": sites_by_band,
        "deviations_by_severity": deviations_by_severity,
        "trend_breakdown": trend_breakdown,
        "capa_summary": capa_summary,
        "top_risk_sites": top_risk_sites,
    }


def _build_rationale(
    factor_breakdown: dict,
    raw: dict,
    sites_by_band: dict,
    deviations_by_severity: dict,
    capa_summary: dict | None,
    total_sites: int,
) -> list[str]:
    """Deterministic, data-cited sentences for the top contributing
    factors -- no free-text generation, so nothing here can hallucinate a
    number that isn't actually in the aggregated data (same guarantee
    Track C's CAPA citations make)."""
    ranked_factors = sorted(factor_breakdown.items(), key=lambda kv: kv[1], reverse=True)
    lines = []
    for key, share in ranked_factors:
        if share <= 0:
            continue
        pct = round(share * 100)
        if key == "avg_site_risk":
            lines.append(
                f"{FACTOR_LABELS[key]} is {round(raw['avg_site_risk'] * 100)}/100 across {total_sites} sites "
                f"— {pct}% of the overall risk index."
            )
        elif key == "high_risk_site_share":
            lines.append(
                f"{sites_by_band['High']} of {total_sites} sites ({round(raw['high_risk_site_share'] * 100)}%) "
                f"are in the High risk band — {pct}% of the overall risk index."
            )
        elif key == "major_deviation_rate":
            lines.append(
                f"{deviations_by_severity['Major']} Major (patient-safety) deviations recorded across the drug's "
                f"site network — {pct}% of the overall risk index."
            )
        elif key == "unresolved_capa_rate" and capa_summary is not None:
            lines.append(
                f"{capa_summary['pending_review'] + capa_summary['rejected']} of {capa_summary['total']} CAPA "
                f"reports are not yet approved (pending: {capa_summary['pending_review']}, "
                f"rejected: {capa_summary['rejected']}) — {pct}% of the overall risk index."
            )
        elif key == "trend_pressure":
            lines.append(
                f"Net site trend is deteriorating: {pct}% of the overall risk index comes from sites trending "
                f"worse rather than better."
            )
    return lines


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
    result = compute_drug_performance(protocol["protocol_id"], ranking, deviations, capa_reports=None)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _main()
