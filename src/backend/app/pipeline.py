"""Orchestration: ingest -> detect -> score -> generate CAPA -> persist.

In-process (docs/03_team_division.md's Track D task 3): calls Track A/B/C's
functions directly rather than making HTTP calls to their standalone
services, so a single POST /pipeline/run is fast and has no network/port
dependencies. Each track's own standalone service (ports 8001-8003) still
exists separately and is unaffected by this.
"""

from __future__ import annotations

from pathlib import Path

from src.capa import corpus as capa_corpus
from src.capa import generator as capa_generator
from src.detection.detector import detect_deviations
from src.risk_scoring import drug_aggregate
from src.risk_scoring.loaders import load_protocol, load_sites, load_visit_records
from src.risk_scoring.scoring import rank_sites

from . import persistence

DEFAULT_DATA_DIR = Path("data/synthetic")

# Site risk bands eligible for an automatic CAPA report -- High only, to
# keep a demo-scale run fast and the CAPA list meaningfully scoped to sites
# that actually need one, matching the "generate CAPA-ready reports for
# high-risk sites" framing in docs/05_api_contracts.md's pipeline endpoint.
CAPA_ELIGIBLE_BANDS = {"High"}


def run_pipeline(protocol_id: str, data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    protocol = load_protocol(data_dir)
    if protocol["protocol_id"] != protocol_id:
        raise ValueError(f"protocol_id '{protocol_id}' not found")

    sites = load_sites(data_dir)
    visit_records = load_visit_records(data_dir)
    site_ids = [s["site_id"] for s in sites]

    deviations = [d.to_dict() for d in detect_deviations(protocol, visit_records)]
    persistence.save_deviations(deviations)

    risk_scores = rank_sites(protocol_id, deviations, visit_records, protocol["visit_schedule"], site_ids)
    persistence.save_risk_scores(risk_scores)

    ich_corpus = capa_corpus.load_ich_corpus()
    devs_by_site: dict[str, list[dict]] = {}
    for d in deviations:
        devs_by_site.setdefault(d["site_id"], []).append(d)

    capa_reports_generated = 0
    for score in risk_scores:
        if score["risk_band"] not in CAPA_ELIGIBLE_BANDS:
            continue
        site_deviations = devs_by_site.get(score["site_id"])
        if not site_deviations:
            continue
        capa_id = persistence.next_capa_id()
        report = capa_generator.generate("site", site_deviations, protocol, ich_corpus, capa_id)
        persistence.save_capa_report(report)
        capa_reports_generated += 1

    result = {
        "status": "completed",
        "sites_processed": len(sites),
        "deviations_found": len(deviations),
        "capa_reports_generated": capa_reports_generated,
    }
    persistence.save_pipeline_run(protocol_id, **{k: v for k, v in result.items() if k != "status"})
    return result


def dashboard_summary(protocol_id: str, data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    """Aggregated view for the Trial Overview screen (05_api_contracts.md).

    Reads persisted results if a pipeline run has already happened for this
    protocol; otherwise runs the pipeline once first so the dashboard is
    never empty on a fresh start.
    """
    if persistence.get_latest_pipeline_run(protocol_id) is None:
        run_pipeline(protocol_id, data_dir)

    sites = load_sites(data_dir)
    patients = _load_json_count(data_dir / "patients.json")
    visit_records = load_visit_records(data_dir)
    ranking = persistence.get_ranking(protocol_id)
    open_deviations = len(persistence.get_all_deviations(protocol_id))
    high_risk_sites = sum(1 for s in ranking if s["risk_band"] == "High")

    return {
        "protocol_id": protocol_id,
        "total_sites": len(sites),
        "total_patients": patients,
        "total_visits": len(visit_records),
        "open_deviations": open_deviations,
        "high_risk_sites": high_risk_sites,
        "site_ranking": [
            {"site_id": s["site_id"], "risk_score": s["risk_score"], "risk_band": s["risk_band"]}
            for s in ranking
        ],
    }


def drug_performance_summary(protocol_id: str, data_dir: Path = DEFAULT_DATA_DIR) -> dict:
    """Drug-level rollup for the Drug Performance screen: aggregates every
    site's persisted risk score plus the drug's deviations and CAPA
    remediation status into one `DrugPerformance` object (see
    `src/risk_scoring/drug_aggregate.py`). This is the "single source of
    truth" view for a regulatory-affairs / trial-sponsor audience -- one
    risk index and readiness verdict per drug, not per site.

    Like `dashboard_summary`, runs the pipeline once first if it hasn't
    run yet so this is never empty on a fresh start.
    """
    if persistence.get_latest_pipeline_run(protocol_id) is None:
        run_pipeline(protocol_id, data_dir)

    sites = load_sites(data_dir)
    visit_records = load_visit_records(data_dir)
    protocol = load_protocol(data_dir)
    site_ids = [s["site_id"] for s in sites]

    ranking = persistence.get_ranking(protocol_id)
    if not ranking:
        deviations = persistence.get_all_deviations(protocol_id) or [
            d.to_dict() for d in detect_deviations(protocol, visit_records)
        ]
        ranking = rank_sites(protocol_id, deviations, visit_records, protocol["visit_schedule"], site_ids)
        persistence.save_risk_scores(ranking)

    deviations = persistence.get_all_deviations(protocol_id)
    capa_reports = [
        {"capa_id": r["capa_id"], "site_id": r["site_id"], "review_status": persistence.get_capa_review(r["capa_id"])["status"]}
        for r in persistence.get_all_capa_reports(protocol_id)
    ]

    return drug_aggregate.compute_drug_performance(protocol_id, ranking, deviations, capa_reports)


def _load_json_count(path: Path) -> int:
    import json

    return len(json.loads(path.read_text(encoding="utf-8")))
