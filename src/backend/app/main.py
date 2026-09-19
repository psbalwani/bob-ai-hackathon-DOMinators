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

Multi-drug: this gateway serves 10 separate protocols/drugs (see
src/data/generate_synthetic_data.py), each a self-contained dataset
directory discovered under DATA_DIR at startup, sharing one physical site
pool. Every route now takes (or resolves) a `protocol_id` and is gated by
`auth.py`'s per-drug-owner login -- a request for a protocol_id the caller
doesn't own 403s, per docs/05_api_contracts.md's updated auth section.
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

# Must run before any local/src import below: db.py reads DATABASE_URL from
# os.environ at *module import time* (so db.USING_DB is fixed once, not
# re-checked per request), so .env has to be loaded first or that flag
# silently freezes as False even with a real DATABASE_URL configured.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / ".env")

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

from src.capa import corpus as capa_corpus
from src.capa import export as capa_export
from src.capa import generator as capa_generator
from src.detection.detector import detect_deviations
from src.risk_scoring.loaders import load_protocol, load_sites, load_visit_records
from src.risk_scoring.scoring import compute_site_risk_score, rank_sites

from . import auth, persistence, pipeline
from .db import init_db
from .errors import ApiError

DATA_DIR = Path("data/synthetic")

app = FastAPI(title="ClinIQ — Track D Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# {protocol_id: {"protocol", "sites", "visit_records", "data_dir"}} -- one
# entry per self-contained dataset directory discovered at startup: the
# top-level DATA_DIR itself (the original single-drug dataset) plus every
# sibling under DATA_DIR/drugs/<protocol_id>/.
_datasets: dict[str, dict] = {}


def _discover_datasets(base_dir: Path) -> dict[str, dict]:
    registry: dict[str, dict] = {}

    def _load(data_dir: Path) -> None:
        if not (data_dir / "protocol.json").exists():
            return
        protocol = load_protocol(data_dir)
        registry[protocol["protocol_id"]] = {
            "protocol": protocol,
            "sites": load_sites(data_dir),
            "visit_records": load_visit_records(data_dir),
            "data_dir": data_dir,
        }

    _load(base_dir)
    drugs_dir = base_dir / "drugs"
    if drugs_dir.is_dir():
        for sub in sorted(drugs_dir.iterdir()):
            if sub.is_dir():
                _load(sub)
    return registry


@app.on_event("startup")
def _startup() -> None:
    global _datasets
    init_db()
    _datasets = _discover_datasets(DATA_DIR)


@app.exception_handler(ApiError)
def _handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


def _get_dataset(protocol_id: str) -> dict:
    ds = _datasets.get(protocol_id)
    if ds is None:
        raise ApiError(404, "NOT_FOUND", f"protocol_id '{protocol_id}' not found")
    return ds


def _authorize(user: auth.User, protocol_id: str) -> dict:
    """Require the dataset to exist AND the caller to own it. Returns the dataset."""
    ds = _get_dataset(protocol_id)
    auth.require_protocol_access(user, protocol_id)
    return ds


def _require_site(ds: dict, site_id: str) -> dict:
    site = next((s for s in ds["sites"] if s["site_id"] == site_id), None)
    if site is None:
        raise ApiError(404, "NOT_FOUND", f"site_id '{site_id}' not found for this protocol")
    return site


def _find_deviation(deviation_id: str) -> tuple[dict | None, dict | None]:
    """Locate a deviation by id across every protocol -- persisted results
    first, then a lazy per-protocol detect as a fallback (mirrors the
    single-protocol fallback the other routes already use)."""
    for d in persistence.get_all_deviations():
        if d["deviation_id"] == deviation_id:
            return d, _datasets.get(d["protocol_id"])
    for protocol_id, ds in _datasets.items():
        for d in detect_deviations(ds["protocol"], ds["visit_records"]):
            d_dict = d.to_dict()
            if d_dict["deviation_id"] == deviation_id:
                return d_dict, ds
    return None, None


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


def _user_payload(user: auth.User) -> dict:
    protocols = [
        {"protocol_id": pid, "title": _datasets[pid]["protocol"]["title"], "drug": _datasets[pid]["protocol"]["dosing_rules"]["drug"]}
        for pid in user.protocol_ids
        if pid in _datasets
    ]
    return {"user_id": user.user_id, "username": user.username, "protocols": protocols}


@app.post("/auth/login")
def post_login(body: LoginRequest) -> dict:
    user = auth.authenticate(body.username, body.password)
    if user is None:
        raise ApiError(401, "UNAUTHORIZED", "invalid username or password")
    return {
        "access_token": auth.create_access_token(user),
        "token_type": "bearer",
        "user": _user_payload(user),
    }


@app.get("/auth/me")
def get_me(user: auth.User = Depends(auth.get_current_user)) -> dict:
    return _user_payload(user)


# ---------------------------------------------------------------------------
# Pipeline / dashboard (docs/05_api_contracts.md Track D section)
# ---------------------------------------------------------------------------


class PipelineRunRequest(BaseModel):
    protocol_id: str


@app.post("/pipeline/run")
def post_pipeline_run(body: PipelineRunRequest, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, body.protocol_id)
    return pipeline.run_pipeline(body.protocol_id, ds["data_dir"])


@app.get("/dashboard/summary")
def get_dashboard_summary(protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    return pipeline.dashboard_summary(protocol_id, ds["data_dir"])


@app.get("/dashboard/drug-performance")
def get_drug_performance(protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    """Drug-level aggregation across every site under this protocol -- the
    single-number/single-verdict view for a regulatory-affairs audience.
    See docs/05_api_contracts.md and src/risk_scoring/drug_aggregate.py."""
    ds = _authorize(user, protocol_id)
    return pipeline.drug_performance_summary(protocol_id, ds["data_dir"])


@app.get("/protocol")
def get_protocol(protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    protocol = ds["protocol"]
    return {
        "protocol_id": protocol["protocol_id"],
        "title": protocol["title"],
        "ich_gcp_version": protocol["ich_gcp_version"],
        "visit_schedule": protocol["visit_schedule"],
        "dosing_rules": protocol["dosing_rules"],
    }


# ---------------------------------------------------------------------------
# Site / patient / visit aggregation for the dashboard drill-downs
# ---------------------------------------------------------------------------


@app.get("/sites")
def list_sites(protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    ranking = {s["site_id"]: s for s in persistence.get_ranking(protocol_id)}
    sites = []
    for s in ds["sites"]:
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
def get_site_detail(site_id: str, protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    site = _require_site(ds, site_id)
    score = persistence.get_risk_score(protocol_id, site_id)
    if score is None:
        score = compute_site_risk_score(
            site_id, protocol_id, persistence.get_all_deviations(protocol_id), ds["visit_records"], ds["protocol"]["visit_schedule"]
        )
    return {
        "site_id": site["site_id"],
        "site_name": site["site_name"],
        "country": site["country"],
        "activation_date": site["activation_date"],
        "risk_score": score,
    }


@app.get("/sites/{site_id}/deviations")
def get_site_deviations(site_id: str, protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    _require_site(ds, site_id)
    deviations = persistence.get_deviations_for_site(site_id, protocol_id)
    if not deviations:
        site_records = [v for v in ds["visit_records"] if v["site_id"] == site_id]
        deviations = [d.to_dict() for d in detect_deviations(ds["protocol"], site_records)]
    return {"deviations": deviations}


@app.get("/sites/{site_id}/visits")
def get_site_visits(site_id: str, protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    _require_site(ds, site_id)
    return {"visits": [v for v in ds["visit_records"] if v["site_id"] == site_id]}


@app.get("/deviations/{deviation_id}")
def get_deviation_detail(deviation_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    deviation, ds = _find_deviation(deviation_id)
    if deviation is None:
        raise ApiError(404, "NOT_FOUND", f"deviation_id '{deviation_id}' not found")
    auth.require_protocol_access(user, deviation["protocol_id"])
    visit = next((v for v in ds["visit_records"] if v["visit_record_id"] == deviation["visit_record_id"]), None)
    return {"deviation": deviation, "visit_record": visit}


@app.get("/sites/{site_id}/capa")
def get_site_capa_reports(site_id: str, protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    _require_site(ds, site_id)
    reports = [r for r in persistence.get_all_capa_reports(protocol_id) if r["site_id"] == site_id]
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
def post_detect(body: DetectRequest, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, body.protocol_id)
    records = ds["visit_records"]
    if body.visit_record_ids is not None:
        wanted = set(body.visit_record_ids)
        records = [r for r in records if r["visit_record_id"] in wanted]
    deviations = [d.to_dict() for d in detect_deviations(ds["protocol"], records)]
    persistence.save_deviations(deviations)
    return {"deviations": deviations}


@app.get("/deviations/site/{site_id}")
def get_deviations_for_site_contract(
    site_id: str, protocol_id: str, user: auth.User = Depends(auth.get_current_user)
) -> dict:
    return get_site_deviations(site_id, protocol_id, user)


# ---------------------------------------------------------------------------
# Track B contract paths (re-exposed in-process)
# ---------------------------------------------------------------------------


class ScoreSiteRequest(BaseModel):
    site_id: str
    protocol_id: str


@app.post("/risk-score/site")
def post_risk_score_site(body: ScoreSiteRequest, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, body.protocol_id)
    _require_site(ds, body.site_id)
    deviations = persistence.get_all_deviations(body.protocol_id) or [
        d.to_dict() for d in detect_deviations(ds["protocol"], ds["visit_records"])
    ]
    score = compute_site_risk_score(body.site_id, body.protocol_id, deviations, ds["visit_records"], ds["protocol"]["visit_schedule"])
    persistence.save_risk_scores([score])
    return score


@app.get("/risk-score/site/{site_id}")
def get_risk_score_site(site_id: str, protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    _require_site(ds, site_id)
    score = persistence.get_risk_score(protocol_id, site_id)
    if score is None:
        deviations = persistence.get_all_deviations(protocol_id) or [
            d.to_dict() for d in detect_deviations(ds["protocol"], ds["visit_records"])
        ]
        score = compute_site_risk_score(site_id, protocol_id, deviations, ds["visit_records"], ds["protocol"]["visit_schedule"])
        persistence.save_risk_scores([score])
    return score


@app.get("/risk-score/ranking")
def get_risk_score_ranking(protocol_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, protocol_id)
    ranking = persistence.get_ranking(protocol_id)
    if not ranking:
        deviations = persistence.get_all_deviations(protocol_id) or [
            d.to_dict() for d in detect_deviations(ds["protocol"], ds["visit_records"])
        ]
        site_ids = sorted(s["site_id"] for s in ds["sites"])
        ranking = rank_sites(protocol_id, deviations, ds["visit_records"], ds["protocol"]["visit_schedule"], site_ids)
        persistence.save_risk_scores(ranking)
    return {
        "sites": [{"site_id": s["site_id"], "risk_score": s["risk_score"], "risk_band": s["risk_band"]} for s in ranking]
    }


# ---------------------------------------------------------------------------
# Track C contract paths (re-exposed in-process)
# ---------------------------------------------------------------------------


class CapaGenerateRequest(BaseModel):
    protocol_id: str
    scope: str
    site_id: str | None = None
    deviation_ids: list[str] | None = None


@app.post("/capa/generate")
def post_capa_generate(body: CapaGenerateRequest, user: auth.User = Depends(auth.get_current_user)) -> dict:
    ds = _authorize(user, body.protocol_id)
    if body.scope not in ("deviation", "site"):
        raise ApiError(400, "VALIDATION_ERROR", "scope must be 'deviation' or 'site'")
    all_devs = persistence.get_all_deviations(body.protocol_id) or [
        d.to_dict() for d in detect_deviations(ds["protocol"], ds["visit_records"])
    ]
    if body.scope == "site":
        if not body.site_id:
            raise ApiError(400, "VALIDATION_ERROR", "site_id is required for scope='site'")
        _require_site(ds, body.site_id)
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
    report = capa_generator.generate(body.scope, deviations, ds["protocol"], ich_corpus, capa_id)
    persistence.save_capa_report(report)
    return report.to_dict()


def _get_owned_capa_report(capa_id: str, user: auth.User) -> dict:
    report = persistence.get_capa_report(capa_id)
    if report is None:
        raise ApiError(404, "NOT_FOUND", f"capa_id '{capa_id}' not found")
    auth.require_protocol_access(user, report["protocol_id"])
    return report


@app.get("/capa/{capa_id}")
def get_capa(capa_id: str, user: auth.User = Depends(auth.get_current_user)) -> dict:
    report = _get_owned_capa_report(capa_id, user)
    review = persistence.get_capa_review(capa_id)
    return {**report, "review_status": review["status"], "reviewer": review["reviewer"], "reviewed_at": review["reviewed_at"]}


class CapaReviewRequest(BaseModel):
    decision: str  # "approve" | "reject"
    reviewer: str | None = None


@app.post("/capa/{capa_id}/review")
def post_capa_review(capa_id: str, body: CapaReviewRequest, user: auth.User = Depends(auth.get_current_user)) -> dict:
    """Human-in-the-loop review gate: a CAPA report is generated as
    pending_review and must be explicitly approved here before it can be
    exported (see export_capa below) -- "finalized," per
    submission.yaml's framing."""
    _get_owned_capa_report(capa_id, user)
    if body.decision not in ("approve", "reject"):
        raise ApiError(400, "VALIDATION_ERROR", "decision must be 'approve' or 'reject'")
    status = "approved" if body.decision == "approve" else "rejected"
    return persistence.set_capa_review(capa_id, status, body.reviewer)


@app.get("/capa/{capa_id}/export")
def export_capa(capa_id: str, format: str = "markdown", user: auth.User = Depends(auth.get_current_user)) -> PlainTextResponse:
    report_dict = _get_owned_capa_report(capa_id, user)
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
