"""SQLAlchemy tables for the three computed-result objects in
docs/04_data_schema.md (sections 3-5): Deviation, Site Risk Score, CapaReport.

Raw input data (protocol spec, patient visit records) stays as the
generated JSON in data/synthetic/ -- that's already this project's source
of truth for input data (see src/data/README.md); these tables persist
*pipeline output* so the dashboard can be served from the database instead
of recomputing on every request.
"""

from __future__ import annotations

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from .db import Base


class DeviationRow(Base):
    __tablename__ = "deviations"

    deviation_id = Column(String, primary_key=True)
    visit_record_id = Column(String, nullable=False)
    patient_id = Column(String, nullable=False)
    site_id = Column(String, nullable=False, index=True)
    protocol_id = Column(String, nullable=False, index=True)
    type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    severity_rationale = Column(String, nullable=False)
    protocol_clause_ref = Column(String, nullable=False)
    detected_at = Column(String, nullable=False)
    detector_version = Column(String, nullable=False)


class SiteRiskScoreRow(Base):
    __tablename__ = "site_risk_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    site_id = Column(String, nullable=False, index=True)
    protocol_id = Column(String, nullable=False, index=True)
    risk_score = Column(Integer, nullable=False)
    risk_band = Column(String, nullable=False)
    computed_at = Column(String, nullable=False)
    indicator_breakdown = Column(JSON, nullable=False)
    trend = Column(String, nullable=False)
    open_deviation_count = Column(Integer, nullable=False)
    total_visits = Column(Integer, nullable=False)


class CapaReportRow(Base):
    __tablename__ = "capa_reports"

    capa_id = Column(String, primary_key=True)
    scope = Column(String, nullable=False)
    site_id = Column(String, nullable=False, index=True)
    related_deviation_ids = Column(JSON, nullable=False)
    root_cause = Column(String, nullable=False)
    corrective_action = Column(String, nullable=False)
    preventive_action = Column(String, nullable=False)
    suggested_owner_role = Column(String, nullable=False)
    suggested_due_window_days = Column(Integer, nullable=False)
    generated_at = Column(String, nullable=False)
    evidence_citations = Column(JSON, nullable=False)


class CapaReviewRow(Base):
    """Human-in-the-loop review gate on a CapaReport, per Track D task list
    ("wire the full pipeline... with a human review checkpoint before
    anything is finalized" -- see submission.yaml's what_we_are_most_proud_of).

    Deliberately a separate table rather than a column on CapaReportRow: the
    review decision is a Track D dashboard-workflow concept layered on top of
    Track C's report, not part of the CapaReport contract itself
    (docs/04_data_schema.md section 5), so this doesn't touch that shape.
    """

    __tablename__ = "capa_reviews"

    capa_id = Column(String, primary_key=True)
    status = Column(String, nullable=False, default="pending_review")  # pending_review | approved | rejected
    reviewer = Column(String, nullable=True)
    reviewed_at = Column(String, nullable=True)


class PipelineRunRow(Base):
    """One row per POST /pipeline/run, for dashboard summary + audit trail."""

    __tablename__ = "pipeline_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    protocol_id = Column(String, nullable=False, index=True)
    ran_at = Column(DateTime(timezone=True), server_default=func.now())
    sites_processed = Column(Integer, nullable=False)
    deviations_found = Column(Integer, nullable=False)
    capa_reports_generated = Column(Integer, nullable=False)
