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
    # Additive field (nothing renamed/removed) so a CAPA report can be
    # attributed to a protocol once sites are shared across multiple
    # protocols/drugs -- see docs/04_data_schema.md section 5. Defaults to
    # "" so existing call sites that construct CapaReport without it (e.g.
    # tests/test_capa_extended.py) keep working unchanged.
    protocol_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


SCOPES = {"deviation", "site"}
