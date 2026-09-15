"""Data shapes for Track C's CAPA generator, mirroring docs/04_data_schema.md section 5."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class CapaReport:
    capa_id: str
    scope: str  # "deviation" | "site"
    site_id: str
    related_deviation_ids: list[str]
    root_cause: str
    corrective_action: str
    preventive_action: str
    suggested_owner_role: str
    suggested_due_window_days: int
    generated_at: str
    evidence_citations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


SCOPES = {"deviation", "site"}
