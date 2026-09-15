"""Orchestrates rules.py + severity.py across a set of visit records."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from . import severity
from .models import Deviation
from .rules import run_all_checks

DETECTOR_VERSION = "rule-v1"


def _stable_deviation_id(visit_record_id: str, deviation_type: str, occurrence: int) -> str:
    """Return a deterministic, collision-free deviation ID.

    BUG-04: a simple per-call counter resets to DEV-000001 on every
    detect_deviations() call, producing 100% ID collisions across calls (e.g.
    CAPA API startup + test fixture both call detect_deviations independently
    and both emit DEV-000001 for the first finding).  Instead we derive the ID
    from the visit record ID, the deviation type, and an intra-record
    occurrence index (for the rare case where the same record produces two
    findings of the same type).  This is stable across runs and processes, so
    DB-persisted storage never sees duplicate keys.
    """
    key = f"{visit_record_id}:{deviation_type}:{occurrence}"
    digest = hashlib.sha1(key.encode()).hexdigest()[:8]
    return f"DEV-{digest}"


def detect_deviations(protocol: dict, visit_records: list[dict]) -> list[Deviation]:
    """Detect + classify deviations for a set of visit records against a protocol.

    Only reads `protocol` and `visit_records` -- never the seeded ground
    truth, which exists solely to score this function's output in tests.
    """
    deviations: list[Deviation] = []
    detected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for record in visit_records:
        # Track per-(record, type) occurrence count so two findings of the same
        # type on the same record get distinct IDs (e.g. two missing_procedures).
        occurrence_counters: dict[str, int] = {}
        for finding in run_all_checks(protocol, record):
            occ = occurrence_counters.get(finding.type, 0)
            occurrence_counters[finding.type] = occ + 1
            sev, rationale, clause_ref = severity.classify(protocol, record, finding)
            deviations.append(
                Deviation(
                    deviation_id=_stable_deviation_id(record["visit_record_id"], finding.type, occ),
                    visit_record_id=record["visit_record_id"],
                    patient_id=record["patient_id"],
                    site_id=record["site_id"],
                    protocol_id=record["protocol_id"],
                    type=finding.type,
                    severity=sev,
                    severity_rationale=rationale,
                    protocol_clause_ref=clause_ref,
                    detected_at=detected_at,
                    detector_version=DETECTOR_VERSION,
                )
            )
    return deviations
