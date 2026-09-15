"""Data shapes for Track A, mirroring docs/04_data_schema.md section 3."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass
class Deviation:
    deviation_id: str
    visit_record_id: str
    patient_id: str
    site_id: str
    protocol_id: str
    type: str
    severity: str
    severity_rationale: str
    protocol_clause_ref: str
    detected_at: str
    detector_version: str

    def to_dict(self) -> dict:
        return asdict(self)


DEVIATION_TYPES = {
    "missed_visit",
    "late_visit",
    "dosage_out_of_range",
    "banned_comedication",
    "missing_procedure",
    "other",
}

SEVERITIES = {"Major", "Minor", "Administrative"}
