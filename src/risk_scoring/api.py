"""Track B's own small FastAPI service — Task 5.

Exposed standalone per docs/03_team_division.md ("Expose the module as its
own small FastAPI endpoint early... so Track D can integrate against it
without waiting") and docs/05_api_contracts.md's Track B section. Track D's
eventual gateway (src/backend, per docs/setup-guide.md) proxies to this
during early integration; this file is not that gateway.

Run standalone:
    uvicorn src.risk_scoring.api:app --reload --port 8002

Data is loaded once at startup from DATA_DIR (default data/synthetic) and
held in memory — no database, consistent with the rest of this hackathon
project. Deviations come from loaders.load_deviations(), which prefers
Track A's real detector snapshot (data/detected/deviations.json) when
present, falling back to the seeded ground truth mock otherwise -- see
loaders.py's module docstring.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .loaders import load_deviations, load_protocol, load_sites, load_visit_records
from .scoring import compute_site_risk_score, rank_sites

DATA_DIR = Path(os.environ.get("RISK_SCORING_DATA_DIR", "data/synthetic"))

app = FastAPI(title="Track B — Site Risk Scoring")

_protocol: dict = {}
_sites: list[dict] = []
_visit_records: list[dict] = []
_deviations: list[dict] = []
_score_cache: dict[str, dict] = {}


@app.on_event("startup")
def _load_data() -> None:
    global _protocol, _sites, _visit_records, _deviations
    _protocol = load_protocol(DATA_DIR)
    _sites = load_sites(DATA_DIR)
    _visit_records = load_visit_records(DATA_DIR)
    _deviations = load_deviations(DATA_DIR)


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


@app.exception_handler(ApiError)
def _handle_api_error(_request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


def _site_ids() -> set[str]:
    return {s["site_id"] for s in _sites}


def _require_known_site(site_id: str) -> None:
    if site_id not in _site_ids():
        raise ApiError(404, "NOT_FOUND", f"site_id '{site_id}' not found")


def _score_site(site_id: str, protocol_id: str) -> dict:
    score = compute_site_risk_score(
        site_id, protocol_id, _deviations, _visit_records, _protocol["visit_schedule"]
    )
    _score_cache[site_id] = score
    return score


class ScoreSiteRequest(BaseModel):
    site_id: str
    protocol_id: str


@app.post("/risk-score/site")
def post_risk_score_site(body: ScoreSiteRequest) -> dict:
    """Computes (or recomputes) the risk score for a site."""
    _require_known_site(body.site_id)
    if body.protocol_id != _protocol["protocol_id"]:
        raise ApiError(400, "VALIDATION_ERROR", f"protocol_id '{body.protocol_id}' not found")
    return _score_site(body.site_id, body.protocol_id)


@app.get("/risk-score/site/{site_id}")
def get_risk_score_site(site_id: str) -> dict:
    """Returns the latest computed score for a site, computing it on first request."""
    _require_known_site(site_id)
    if site_id not in _score_cache:
        _score_site(site_id, _protocol["protocol_id"])
    return _score_cache[site_id]


@app.get("/risk-score/ranking")
def get_risk_score_ranking(protocol_id: str) -> dict:
    """Returns all sites for a protocol, ranked by risk_score descending."""
    if protocol_id != _protocol["protocol_id"]:
        raise ApiError(400, "VALIDATION_ERROR", f"protocol_id '{protocol_id}' not found")
    ranking = rank_sites(
        protocol_id,
        _deviations,
        _visit_records,
        _protocol["visit_schedule"],
        sorted(_site_ids()),
    )
    for score in ranking:
        _score_cache[score["site_id"]] = score
    return {
        "sites": [
            {"site_id": s["site_id"], "risk_score": s["risk_score"], "risk_band": s["risk_band"]}
            for s in ranking
        ]
    }
