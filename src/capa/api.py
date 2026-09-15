"""FastAPI app for Track C's CAPA generator -- see docs/05_api_contracts.md.

Loads the real synthetic dataset and runs Track A's actual detector
(src/detection/detector.py) once at startup to get real Deviation objects --
no mocking needed now that Track A is live. Track B's risk scorer isn't
called here: the CapaReport contract (04_data_schema.md section 5) doesn't
carry risk-score fields, and severity already drives owner/due-window in
templates.py; site risk score remains available separately via Track B's own
`GET /risk-score/site/{site_id}` for the dashboard to show alongside a CAPA.

Run with:
    python -m uvicorn src.capa.api:app --reload --port 8003
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel

from ..detection.detector import detect_deviations
from . import corpus, generator, store

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

SYNTHETIC_DIR = Path("data/synthetic")

_protocol: dict | None = None
_ich_corpus: dict[str, dict] = {}
_deviations_by_id: dict[str, dict] = {}
_deviations_by_site: dict[str, list[dict]] = {}
_site_ids: set[str] = set()


def _load_dataset() -> None:
    global _protocol, _ich_corpus, _deviations_by_id, _deviations_by_site, _site_ids
    _ich_corpus = corpus.load_ich_corpus()
    if not (SYNTHETIC_DIR / "protocol.json").exists():
        return
    _protocol = json.loads((SYNTHETIC_DIR / "protocol.json").read_text(encoding="utf-8"))
    visit_records = json.loads((SYNTHETIC_DIR / "visit_records.json").read_text(encoding="utf-8"))
    sites = json.loads((SYNTHETIC_DIR / "sites.json").read_text(encoding="utf-8"))
    _site_ids = {s["site_id"] for s in sites}

    deviations = [d.to_dict() for d in detect_deviations(_protocol, visit_records)]
    _deviations_by_id = {d["deviation_id"]: d for d in deviations}
    _deviations_by_site = {}
    for d in deviations:
        _deviations_by_site.setdefault(d["site_id"], []).append(d)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_dataset()
    yield


app = FastAPI(title="Track C - CAPA Generation", lifespan=lifespan)


def _error(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail
    from fastapi.responses import JSONResponse

    body = _error(detail["code"], detail["message"]) if isinstance(detail, dict) and "code" in detail else _error("ERROR", str(detail))
    return JSONResponse(status_code=exc.status_code, content=body)


def _require_dataset() -> None:
    if _protocol is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": "no dataset loaded (data/synthetic/ missing)"},
        )


class GenerateRequest(BaseModel):
    scope: str
    site_id: str | None = None
    deviation_ids: list[str] | None = None


@app.post("/capa/generate")
def generate_capa(req: GenerateRequest):
    _require_dataset()
    if req.scope not in ("deviation", "site"):
        raise HTTPException(
            status_code=400,
            detail={"code": "VALIDATION_ERROR", "message": "scope must be 'deviation' or 'site'"},
        )

    if req.scope == "deviation":
        if not req.deviation_ids or len(req.deviation_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail={"code": "VALIDATION_ERROR", "message": "scope='deviation' requires exactly one deviation_ids entry"},
            )
        dev_id = req.deviation_ids[0]
        deviation = _deviations_by_id.get(dev_id)
        if deviation is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"unknown deviation_id: {dev_id}"},
            )
        resolved = [deviation]
    else:
        if not req.site_id:
            raise HTTPException(
                status_code=400,
                detail={"code": "VALIDATION_ERROR", "message": "scope='site' requires site_id"},
            )
        if req.site_id not in _site_ids:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"unknown site_id: {req.site_id}"},
            )
        site_deviations = _deviations_by_site.get(req.site_id, [])
        if req.deviation_ids:
            wanted = set(req.deviation_ids)
            unknown = wanted - {d["deviation_id"] for d in site_deviations}
            if unknown:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "NOT_FOUND", "message": f"deviation_ids not found at {req.site_id}: {sorted(unknown)}"},
                )
            resolved = [d for d in site_deviations if d["deviation_id"] in wanted]
        else:
            resolved = site_deviations
        if not resolved:
            raise HTTPException(
                status_code=400,
                detail={"code": "VALIDATION_ERROR", "message": f"no deviations found for site {req.site_id}; nothing to report"},
            )

    report = generator.generate(req.scope, resolved, _protocol, _ich_corpus, store.next_capa_id())
    store.save(report)
    store.save_snapshot()
    return report.to_dict()


@app.get("/capa/{capa_id}")
def get_capa(capa_id: str):
    report = store.get(capa_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"unknown capa_id: {capa_id}"},
        )
    return report.to_dict()


@app.get("/capa/{capa_id}/export")
def export_capa(capa_id: str, format: str = "markdown"):
    if format not in ("pdf", "markdown"):
        raise HTTPException(
            status_code=400,
            detail={"code": "VALIDATION_ERROR", "message": "format must be 'pdf' or 'markdown'"},
        )
    report = store.get(capa_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "NOT_FOUND", "message": f"unknown capa_id: {capa_id}"},
        )

    from . import export

    if format == "markdown":
        return Response(content=export.to_markdown(report), media_type="text/markdown")

    pdf_bytes = export.to_pdf_bytes(report)
    if pdf_bytes is None:
        raise HTTPException(
            status_code=501,
            detail={"code": "NOT_IMPLEMENTED", "message": "PDF export requires the optional 'fpdf2' package; markdown export is always available"},
        )
    return Response(content=pdf_bytes, media_type="application/pdf")
