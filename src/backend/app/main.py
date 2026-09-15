"""Track D gateway -- wires Tracks A/B/C behind one API for the dashboard.

Run with:
    uvicorn src.backend.app.main:app --reload --port 8000

Endpoints from docs/05_api_contracts.md's Track D section
(POST /pipeline/run, GET /dashboard/summary) plus the aggregation endpoints
the React dashboard needs (sites/visits/deviations/capa detail) that the
contract doesn't spell out field-by-field but scopes to this track
("Orchestration / Dashboard Aggregation"). Tracks A/B/C's own contract
paths (POST /deviations/detect, POST /risk-score/site, POST /capa/generate,
etc.) are also re-exposed here so the frontend only needs one base URL --
each track's own standalone service (ports 8001-8003) still exists
separately for early integration testing per docs/03_team_division.md.
"""

from __future__ import annotations

import json
from pathlib import Path

from dotenv import load_dotenv

# Must run before any local/src import below: db.py reads DATABASE_URL from
# os.environ at *module import time* (so db.USING_DB is fixed once, not
# re-checked per request), so .env has to be loaded first or that flag
# silently freezes as False even with a real DATABASE_URL configured.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from src.capa import corpus as capa_corpus
from src.capa import export as capa_export
from src.capa import generator as capa_generator
from src.detection.detector import detect_deviations
from src.risk_scoring.loaders import load_protocol, load_sites, load_visit_records
from src.risk_scoring.scoring import compute_site_risk_score, rank_sites

from . import persistence, pipeline
from .db import init_db

DATA_DIR = Path("data/synthetic")

app = FastAPI(title="ClinIQ — Track D Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_protocol: dict = {}
_sites: list[dict] = []
_visit_records: list[dict] = []


@app.on_event("startup")
def _startup() -> None:
    global _protocol, _sites, _visit_records
    init_db()
    if (DATA_DIR / "protocol.json").exists():
        _protocol = load_protocol(DATA_DIR)
        _sites = load_sites(DATA_DIR)
        _visit_records = load_visit_records(DATA_DIR)


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


@app.exception_handler(ApiError)
def _handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


def _require_dataset() -> None:
    if not _protocol:
        raise ApiError(404, "NOT_FOUND", "no dataset loaded (data/synthetic/ missing)")


def _require_protocol(protocol_id: str) -> None:
    _require_dataset()
    if protocol_id != _protocol["protocol_id"]:
        raise ApiError(400, "VALIDATION_ERROR", f"protocol_id '{protocol_id}' not found")


def _site_ids() -> set[str]:
    return {s["site_id"] for s in _sites}


def _require_site(site_id: str) -> None:
    _require_dataset()
    if site_id not in _site_ids():
        raise ApiError(404, "NOT_FOUND", f"site_id '{site_id}' not found")


# ---------------------------------------------------------------------------
# Pipeline / dashboard (docs/05_api_contracts.md Track D section)
# ---------------------------------------------------------------------------


class PipelineRunRequest(BaseModel):
    protocol_id: str


@app.post("/pipeline/run")
def post_pipeline_run(body: PipelineRunRequest) -> dict:
    _require_protocol(body.protocol_id)
    return pipeline.run_pipeline(body.protocol_id, DATA_DIR)


@app.get("/dashboard/summary")
def get_dashboard_summary(protocol_id: str) -> dict:
    _require_protocol(protocol_id)
    return pipeline.dashboard_summary(protocol_id, DATA_DIR)


@app.get("/protocol")
def get_protocol() -> dict:
    _require_dataset()
    return {
        "protocol_id": _protocol["protocol_id"],
        "title": _protocol["title"],
        "ich_gcp_version": _protocol["ich_gcp_version"],
        "visit_schedule": _protocol["visit_schedule"],
    }


# ---------------------------------------------------------------------------
# Site / patient / visit aggregation for the dashboard drill-downs
# ---------------------------------------------------------------------------


@app.get("/sites")
def list_sites(protocol_id: str) -> dict:
    _require_protocol(protocol_id)
    ranking = {s["site_id"]: s for s in persistence.get_ranking(protocol_id)}
    sites = []
    for s in _sites:
        score = ranking.get(s["site_id"])
        sites.append(
            {
                "site_id": s["site_id"],
                "site_name": s["site_name"],
                "country": s["country"],
                "risk_score": score["risk_score"] if score else None,
                "risk_band": score["risk_band"] if score else None,
                "trend": score["trend"] if score else None,
                "open_deviation_count": score["open_deviation_count"] if score else 0,
            }
        )
    sites.sort(key=lambda s: (s["risk_score"] is None, -(s["risk_score"] or 0)))
    return {"sites": sites}


@app.get("/sites/{site_id}")
def get_site_detail(site_id: str) -> dict:
    _require_site(site_id)
    site = next(s for s in _sites if s["site_id"] == site_id)
    score = persistence.get_risk_score(site_id)
    if score is None:
        score = compute_site_risk_score(
            site_id, _protocol["protocol_id"], persistence.get_all_deviations(), _visit_records, _protocol["visit_schedule"]
        )
    return {
        "site_id": site["site_id"],
        "site_name": site["site_name"],
        "country": site["country"],
        "activation_date": site["activation_date"],
        "risk_score": score,
    }


@app.get("/sites/{site_id}/deviations")
def get_site_deviations(site_id: str) -> dict:
    _require_site(site_id)
    deviations = persistence.get_deviations_for_site(site_id)
    if not deviations:
        site_records = [v for v in _visit_records if v["site_id"] == site_id]
        deviations = [d.to_dict() for d in detect_deviations(_protocol, site_records)]
    return {"deviations": deviations}


@app.get("/sites/{site_id}/visits")
def get_site_visits(site_id: str) -> dict:
    _require_site(site_id)
    return {"visits": [v for v in _visit_records if v["site_id"] == site_id]}


@app.get("/deviations/{deviation_id}")
def get_deviation_detail(deviation_id: str) -> dict:
    _require_dataset()
    all_devs = persistence.get_all_deviations() or [
        d.to_dict() for d in detect_deviations(_protocol, _visit_records)
    ]
    deviation = next((d for d in all_devs if d["deviation_id"] == deviation_id), None)
    if deviation is None:
        raise ApiError(404, "NOT_FOUND", f"deviation_id '{deviation_id}' not found")
    visit = next((v for v in _visit_records if v["visit_record_id"] == deviation["visit_record_id"]), None)
    return {"deviation": deviation, "visit_record": visit}


@app.get("/sites/{site_id}/capa")
def get_site_capa_reports(site_id: str) -> dict:
    _require_site(site_id)
    reports = [r for r in persistence.get_all_capa_reports() if r["site_id"] == site_id]
    enriched = []
    for r in reports:
        review = persistence.get_capa_review(r["capa_id"])
        enriched.append({**r, "review_status": review["status"], "reviewer": review["reviewer"], "reviewed_at": review["reviewed_at"]})
    return {"capa_reports": enriched}


# ---------------------------------------------------------------------------
# Track A contract paths (re-exposed in-process)
# ---------------------------------------------------------------------------


class DetectRequest(BaseModel):
    protocol_id: str
    visit_record_ids: list[str] | None = None


@app.post("/deviations/detect")
def post_detect(body: DetectRequest) -> dict:
    _require_protocol(body.protocol_id)
    records = _visit_records
    if body.visit_record_ids is not None:
        wanted = set(body.visit_record_ids)
        records = [r for r in records if r["visit_record_id"] in wanted]
    deviations = [d.to_dict() for d in detect_deviations(_protocol, records)]
    persistence.save_deviations(deviations)
    return {"deviations": deviations}


@app.get("/deviations/site/{site_id}")
def get_deviations_for_site_contract(site_id: str) -> dict:
    return get_site_deviations(site_id)


# ---------------------------------------------------------------------------
# Track B contract paths (re-exposed in-process)
# ---------------------------------------------------------------------------


class ScoreSiteRequest(BaseModel):
    site_id: str
    protocol_id: str


@app.post("/risk-score/site")
def post_risk_score_site(body: ScoreSiteRequest) -> dict:
    _require_site(body.site_id)
    _require_protocol(body.protocol_id)
    deviations = persistence.get_all_deviations() or [d.to_dict() for d in detect_deviations(_protocol, _visit_records)]
    score = compute_site_risk_score(body.site_id, body.protocol_id, deviations, _visit_records, _protocol["visit_schedule"])
    persistence.save_risk_scores([score])
    return score


@app.get("/risk-score/site/{site_id}")
def get_risk_score_site(site_id: str) -> dict:
    _require_site(site_id)
    score = persistence.get_risk_score(site_id)
    if score is None:
        deviations = persistence.get_all_deviations() or [d.to_dict() for d in detect_deviations(_protocol, _visit_records)]
        score = compute_site_risk_score(
            site_id, _protocol["protocol_id"], deviations, _visit_records, _protocol["visit_schedule"]
        )
        persistence.save_risk_scores([score])
    return score


@app.get("/risk-score/ranking")
def get_risk_score_ranking(protocol_id: str) -> dict:
    _require_protocol(protocol_id)
    ranking = persistence.get_ranking(protocol_id)
    if not ranking:
        deviations = persistence.get_all_deviations() or [d.to_dict() for d in detect_deviations(_protocol, _visit_records)]
        ranking = rank_sites(protocol_id, deviations, _visit_records, _protocol["visit_schedule"], sorted(_site_ids()))
        persistence.save_risk_scores(ranking)
    return {
        "sites": [{"site_id": s["site_id"], "risk_score": s["risk_score"], "risk_band": s["risk_band"]} for s in ranking]
    }


# ---------------------------------------------------------------------------
# Track C contract paths (re-exposed in-process)
# ---------------------------------------------------------------------------


class CapaGenerateRequest(BaseModel):
    scope: str
    site_id: str | None = None
    deviation_ids: list[str] | None = None


@app.post("/capa/generate")
def post_capa_generate(body: CapaGenerateRequest) -> dict:
    _require_dataset()
    if body.scope not in ("deviation", "site"):
        raise ApiError(400, "VALIDATION_ERROR", "scope must be 'deviation' or 'site'")
    all_devs = persistence.get_all_deviations() or [d.to_dict() for d in detect_deviations(_protocol, _visit_records)]
    if body.scope == "site":
        if not body.site_id:
            raise ApiError(400, "VALIDATION_ERROR", "site_id is required for scope='site'")
        _require_site(body.site_id)
        deviations = [d for d in all_devs if d["site_id"] == body.site_id]
        if body.deviation_ids:
            wanted = set(body.deviation_ids)
            deviations = [d for d in deviations if d["deviation_id"] in wanted]
    else:
        if not body.deviation_ids or len(body.deviation_ids) != 1:
            raise ApiError(400, "VALIDATION_ERROR", "scope='deviation' requires exactly one deviation_id")
        deviations = [d for d in all_devs if d["deviation_id"] == body.deviation_ids[0]]

    if not deviations:
        raise ApiError(404, "NOT_FOUND", "no matching deviations found")

    ich_corpus = capa_corpus.load_ich_corpus()
    capa_id = persistence.next_capa_id()
    report = capa_generator.generate(body.scope, deviations, _protocol, ich_corpus, capa_id)
    persistence.save_capa_report(report)
    return report.to_dict()


@app.get("/capa/{capa_id}")
def get_capa(capa_id: str) -> dict:
    report = persistence.get_capa_report(capa_id)
    if report is None:
        raise ApiError(404, "NOT_FOUND", f"capa_id '{capa_id}' not found")
    review = persistence.get_capa_review(capa_id)
    return {**report, "review_status": review["status"], "reviewer": review["reviewer"], "reviewed_at": review["reviewed_at"]}


class CapaReviewRequest(BaseModel):
    decision: str  # "approve" | "reject"
    reviewer: str | None = None


@app.post("/capa/{capa_id}/review")
def post_capa_review(capa_id: str, body: CapaReviewRequest) -> dict:
    """Human-in-the-loop review gate: a CAPA report is generated as
    pending_review and must be explicitly approved here before it can be
    exported (see export_capa below) -- "finalized," per
    submission.yaml's framing."""
    if persistence.get_capa_report(capa_id) is None:
        raise ApiError(404, "NOT_FOUND", f"capa_id '{capa_id}' not found")
    if body.decision not in ("approve", "reject"):
        raise ApiError(400, "VALIDATION_ERROR", "decision must be 'approve' or 'reject'")
    status = "approved" if body.decision == "approve" else "rejected"
    return persistence.set_capa_review(capa_id, status, body.reviewer)


@app.get("/capa/{capa_id}/export")
def export_capa(capa_id: str, format: str = "markdown") -> PlainTextResponse:
    report_dict = persistence.get_capa_report(capa_id)
    if report_dict is None:
        raise ApiError(404, "NOT_FOUND", f"capa_id '{capa_id}' not found")
    review = persistence.get_capa_review(capa_id)
    if review["status"] != "approved":
        raise ApiError(
            403,
            "NOT_APPROVED",
            f"CAPA report '{capa_id}' must be approved (current status: {review['status']}) before it can be exported",
        )
    from src.capa.models import CapaReport

    report = CapaReport(**report_dict)
    if format == "markdown":
        return PlainTextResponse(capa_export.to_markdown(report), media_type="text/markdown")
    if format == "pdf":
        pdf_bytes = capa_export.to_pdf_bytes(report)
        if pdf_bytes is None:
            raise ApiError(501, "NOT_IMPLEMENTED", "PDF export requires the optional fpdf2 dependency")
        return PlainTextResponse(content=pdf_bytes, media_type="application/pdf")
    raise ApiError(400, "VALIDATION_ERROR", "format must be 'markdown' or 'pdf'")
