"""Orchestrates rules.py + severity.py across a set of visit records."""

from __future__ import annotations

from datetime import datetime, timezone

from . import severity
from .models import Deviation
from .rules import run_all_checks

DETECTOR_VERSION = "rule-v1"


def detect_deviations(protocol: dict, visit_records: list[dict]) -> list[Deviation]:
    """Detect + classify deviations for a set of visit records against a protocol.

    Only reads `protocol` and `visit_records` -- never the seeded ground
    truth, which exists solely to score this function's output in tests.
    """
    deviations: list[Deviation] = []
    counter = 1
    detected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for record in visit_records:
        for finding in run_all_checks(protocol, record):
            sev, rationale, clause_ref = severity.classify(protocol, record, finding)
            deviations.append(
                Deviation(
                    deviation_id=f"DEV-{counter:06d}",
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
            counter += 1

    return deviations
