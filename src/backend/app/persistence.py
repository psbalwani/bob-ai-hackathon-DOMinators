"""Unified persistence interface: real Postgres if DATABASE_URL is set,
otherwise an in-memory store -- callers (pipeline.py, main.py's routes)
don't need to know which one is active.
"""

from __future__ import annotations

from datetime import datetime, timezone

from . import db

if db.USING_DB:
    from .models_db import CapaReportRow, CapaReviewRow, DeviationRow, PipelineRunRow, SiteRiskScoreRow

VALID_REVIEW_STATUSES = {"pending_review", "approved", "rejected"}

# In-memory fallback state, keyed the same way the DB tables would be.
_mem_deviations: dict[str, dict] = {}
_mem_risk_scores: dict[tuple[str, str], dict] = {}  # keyed by (protocol_id, site_id), latest wins
_mem_capa_reports: dict[str, dict] = {}
_mem_capa_reviews: dict[str, dict] = {}
_mem_pipeline_runs: list[dict] = []
_mem_capa_counter = 0


def is_db_configured() -> bool:
    return db.USING_DB


def next_capa_id() -> str:
    if db.USING_DB:
        with db.SessionLocal() as session:
            count = session.query(CapaReportRow).count()
        return f"CAPA-{count + 1:06d}"
    global _mem_capa_counter
    _mem_capa_counter += 1
    return f"CAPA-{_mem_capa_counter:06d}"


def save_deviations(deviations: list[dict]) -> None:
    if db.USING_DB:
        with db.SessionLocal() as session:
            for d in deviations:
                session.merge(DeviationRow(**d))
            session.commit()
        return
    for d in deviations:
        _mem_deviations[d["deviation_id"]] = d


def save_risk_scores(scores: list[dict]) -> None:
    if db.USING_DB:
        with db.SessionLocal() as session:
            for s in scores:
                session.query(SiteRiskScoreRow).filter_by(site_id=s["site_id"], protocol_id=s["protocol_id"]).delete()
                session.add(SiteRiskScoreRow(**{k: v for k, v in s.items() if k != "id"}))
            session.commit()
        return
    for s in scores:
        _mem_risk_scores[(s["protocol_id"], s["site_id"])] = s


def save_capa_report(report) -> None:
    """`report` is a src.capa.models.CapaReport dataclass. Seeds a
    pending_review row so every new report starts gated, not silently
    finalized."""
    data = report.to_dict()
    if db.USING_DB:
        with db.SessionLocal() as session:
            session.merge(CapaReportRow(**data))
            if session.get(CapaReviewRow, data["capa_id"]) is None:
                session.add(CapaReviewRow(capa_id=data["capa_id"], status="pending_review"))
            session.commit()
        return
    _mem_capa_reports[data["capa_id"]] = data
    _mem_capa_reviews.setdefault(
        data["capa_id"], {"capa_id": data["capa_id"], "status": "pending_review", "reviewer": None, "reviewed_at": None}
    )


def get_capa_review(capa_id: str) -> dict:
    if db.USING_DB:
        with db.SessionLocal() as session:
            row = session.get(CapaReviewRow, capa_id)
            if row is None:
                return {"capa_id": capa_id, "status": "pending_review", "reviewer": None, "reviewed_at": None}
            return _row_to_dict(row)
    return _mem_capa_reviews.get(
        capa_id, {"capa_id": capa_id, "status": "pending_review", "reviewer": None, "reviewed_at": None}
    )


def set_capa_review(capa_id: str, status: str, reviewer: str | None) -> dict:
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"invalid review status: {status}")
    reviewed_at = datetime.now(timezone.utc).isoformat()
    review = {"capa_id": capa_id, "status": status, "reviewer": reviewer, "reviewed_at": reviewed_at}
    if db.USING_DB:
        with db.SessionLocal() as session:
            session.merge(CapaReviewRow(**review))
            session.commit()
        return review
    _mem_capa_reviews[capa_id] = review
    return review


def save_pipeline_run(protocol_id: str, sites_processed: int, deviations_found: int, capa_reports_generated: int) -> None:
    if db.USING_DB:
        with db.SessionLocal() as session:
            session.add(
                PipelineRunRow(
                    protocol_id=protocol_id,
                    sites_processed=sites_processed,
                    deviations_found=deviations_found,
                    capa_reports_generated=capa_reports_generated,
                )
            )
            session.commit()
        return
    _mem_pipeline_runs.append(
        {
            "protocol_id": protocol_id,
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "sites_processed": sites_processed,
            "deviations_found": deviations_found,
            "capa_reports_generated": capa_reports_generated,
        }
    )


def _row_to_dict(row, exclude: set[str] = frozenset()) -> dict:
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in exclude}


def get_deviations_for_site(site_id: str, protocol_id: str) -> list[dict]:
    if db.USING_DB:
        with db.SessionLocal() as session:
            rows = session.query(DeviationRow).filter_by(site_id=site_id, protocol_id=protocol_id).all()
            return [_row_to_dict(r) for r in rows]
    return [d for d in _mem_deviations.values() if d["site_id"] == site_id and d["protocol_id"] == protocol_id]


def get_all_deviations(protocol_id: str | None = None) -> list[dict]:
    if db.USING_DB:
        with db.SessionLocal() as session:
            q = session.query(DeviationRow)
            if protocol_id:
                q = q.filter_by(protocol_id=protocol_id)
            return [_row_to_dict(r) for r in q.all()]
    devs = list(_mem_deviations.values())
    return [d for d in devs if not protocol_id or d["protocol_id"] == protocol_id]


def get_risk_score(protocol_id: str, site_id: str) -> dict | None:
    if db.USING_DB:
        with db.SessionLocal() as session:
            row = session.query(SiteRiskScoreRow).filter_by(site_id=site_id, protocol_id=protocol_id).first()
            return _row_to_dict(row, exclude={"id"}) if row else None
    return _mem_risk_scores.get((protocol_id, site_id))


def get_ranking(protocol_id: str) -> list[dict]:
    if db.USING_DB:
        with db.SessionLocal() as session:
            rows = (
                session.query(SiteRiskScoreRow)
                .filter_by(protocol_id=protocol_id)
                .order_by(SiteRiskScoreRow.risk_score.desc())
                .all()
            )
            return [_row_to_dict(r, exclude={"id"}) for r in rows]
    scores = [s for s in _mem_risk_scores.values() if s["protocol_id"] == protocol_id]
    return sorted(scores, key=lambda s: s["risk_score"], reverse=True)


def get_capa_report(capa_id: str) -> dict | None:
    if db.USING_DB:
        with db.SessionLocal() as session:
            row = session.query(CapaReportRow).filter_by(capa_id=capa_id).first()
            return _row_to_dict(row) if row else None
    return _mem_capa_reports.get(capa_id)


def get_all_capa_reports(protocol_id: str | None = None) -> list[dict]:
    if db.USING_DB:
        with db.SessionLocal() as session:
            q = session.query(CapaReportRow)
            if protocol_id:
                q = q.filter_by(protocol_id=protocol_id)
            return [_row_to_dict(r) for r in q.all()]
    reports = list(_mem_capa_reports.values())
    return [r for r in reports if not protocol_id or r.get("protocol_id") == protocol_id]


def get_latest_pipeline_run(protocol_id: str) -> dict | None:
    if db.USING_DB:
        with db.SessionLocal() as session:
            row = (
                session.query(PipelineRunRow)
                .filter_by(protocol_id=protocol_id)
                .order_by(PipelineRunRow.ran_at.desc())
                .first()
            )
            return _row_to_dict(row, exclude={"id"}) if row else None
    runs = [r for r in _mem_pipeline_runs if r["protocol_id"] == protocol_id]
    return runs[-1] if runs else None
