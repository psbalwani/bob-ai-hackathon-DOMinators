"""FastAPI app for Track A -- see docs/05_api_contracts.md.

Run with:
    python -m uvicorn src.detection.api:app --reload --port 8001

Against the full-scale dataset instead of the demo one:
    DETECTION_DATA_DIR=data/synthetic_fullscale python -m uvicorn src.detection.api:app --reload --port 8001
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from . import store
from .detector import detect_deviations

# Load src/.env (WATSONX_API_KEY etc.) before any request touches llm_hook.py.
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

SYNTHETIC_DIR = Path(os.environ.get("DETECTION_DATA_DIR", "data/synthetic"))


def _snapshot_path() -> Path:
    """Where this run's snapshot should land, derived from SYNTHETIC_DIR.

    Same convention as src/risk_scoring/loaders.py's _detected_snapshot_path
    -- data/synthetic -> data/detected, data/synthetic_fullscale ->
    data/detected_fullscale -- so a non-default DETECTION_DATA_DIR doesn't
    silently overwrite the demo snapshot (or get silently ignored by a
    consumer looking for a sibling-named detected dir). Keep both in sync
    if this convention ever changes.
    """
    detected_dir_name = SYNTHETIC_DIR.name.replace("synthetic", "detected")
    return SYNTHETIC_DIR.parent / detected_dir_name / "deviations.json"


_protocol: dict | None = None
_visit_records: list[dict] = []
_site_ids: set[str] = set()


def _load_dataset() -> None:
    global _protocol, _visit_records, _site_ids
    if not (SYNTHETIC_DIR / "protocol.json").exists():
        return
    _protocol = json.loads((SYNTHETIC_DIR / "protocol.json").read_text(encoding="utf-8"))
    _visit_records = json.loads((SYNTHETIC_DIR / "visit_records.json").read_text(encoding="utf-8"))
    sites = json.loads((SYNTHETIC_DIR / "sites.json").read_text(encoding="utf-8"))
    _site_ids = {s["site_id"] for s in sites}


def _run_detection(visit_record_ids: list[str] | None = None) -> list:
    if _protocol is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"no dataset loaded ({SYNTHETIC_DIR}/ missing)"},
        )
    if visit_record_ids is None:
        records = _visit_records
    else:
        wanted = set(visit_record_ids)
        records = [r for r in _visit_records if r["visit_record_id"] in wanted]

    deviations = detect_deviations(_protocol, records)
    considered_ids = {r["visit_record_id"] for r in records}
    store.replace_for_records(deviations, considered_ids)
    store.save_snapshot(path=_snapshot_path())
    return deviations


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_dataset()
    if _protocol is not None:
        _run_detection()
    yield


app = FastAPI(title="Track A - Deviation Detection", lifespan=lifespan)


def _error(code: str, message: str):
    return {"error": {"code": code, "message": message}}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        body = {"error": detail}
    else:
        body = _error("ERROR", str(detail))
    return JSONResponse(status_code=exc.status_code, content=body)


class DetectRequest(BaseModel):
    protocol_id: str
    visit_record_ids: list[str] | None = None


@app.post("/deviations/detect")
def detect(req: DetectRequest):
    if _protocol is None:
        # BUG-06: use the actual SYNTHETIC_DIR so the message stays correct when
        # DETECTION_DATA_DIR env var is overridden (not always "data/synthetic/").
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"no dataset loaded ({SYNTHETIC_DIR}/ missing)"},
        )
    if req.protocol_id != _protocol["protocol_id"]:
        raise HTTPException(
            status_code=400,
            detail={"code": "VALIDATION_ERROR", "message": "protocol_id not found"},
        )
    deviations = _run_detection(req.visit_record_ids)
    return {"deviations": [d.to_dict() for d in deviations]}


@app.get("/deviations/site/{site_id}")
def get_site_deviations(site_id: str):
    if site_id not in _site_ids:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"unknown site_id: {site_id}"},
        )
    deviations = store.for_site(site_id) or []
    return {"deviations": [d.to_dict() for d in deviations]}
