"""Data loading for Track B, decoupled from Track A's detector being ready.

`load_deviations` accepts anything already shaped like the `Deviation` object
in docs/04_data_schema.md section 3 (i.e. Track A's real
`POST /deviations/detect` output). Until that endpoint exists,
`mock_deviations_from_seed` adapts Track C's ground-truth seed file
(`seeded_deviations_ground_truth.json`) into the same shape, per the
team-division note: "can build against mocked deviations until Track A is
ready."
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def load_protocol(data_dir: Path) -> dict:
    return _load_json(data_dir / "protocol.json")


def load_sites(data_dir: Path) -> list[dict]:
    return _load_json(data_dir / "sites.json")


def load_visit_records(data_dir: Path) -> list[dict]:
    return _load_json(data_dir / "visit_records.json")


# Same severity points used for scoring in indicators.py — kept here too so
# the mock adapter and the scorer can't silently drift apart.
SEVERITY_RATIONALE_DEFAULT = "Severity per seeded ground-truth expectation (mock detector output)."


def mock_deviations_from_seed(data_dir: Path) -> list[dict]:
    """Adapt seeded_deviations_ground_truth.json rows into Deviation-shaped dicts.

    Ground-truth rows use `seed_id`/`expected_severity` (not
    `deviation_id`/`severity`) precisely so they never collide with a real
    detector's output (see src/data/README.md) — this adapter is the
    translation layer, used only until Track A's endpoint is live.
    """
    seed_rows = _load_json(data_dir / "seeded_deviations_ground_truth.json")
    visits_by_id = {v["visit_record_id"]: v for v in load_visit_records(data_dir)}

    deviations = []
    for row in seed_rows:
        visit = visits_by_id.get(row["visit_record_id"])
        detected_at_date = (visit or {}).get("actual_date") or (visit or {}).get("scheduled_date")
        deviations.append(
            {
                "deviation_id": row["seed_id"],
                "visit_record_id": row["visit_record_id"],
                "patient_id": row["patient_id"],
                "site_id": row["site_id"],
                "protocol_id": row["protocol_id"],
                "type": row["type"],
                "severity": row["expected_severity"],
                "severity_rationale": row.get("severity_rationale_hint", SEVERITY_RATIONALE_DEFAULT),
                "protocol_clause_ref": row.get("protocol_clause_ref", ""),
                "detected_at": f"{detected_at_date}T00:00:00Z" if detected_at_date else None,
                "detector_version": "mock-seed-v1",
            }
        )
    return deviations


def load_deviations(data_dir: Path, deviations: list[dict] | None = None) -> list[dict]:
    """Return Deviation-shaped dicts: real ones if passed in, else the mock adapter."""
    if deviations is not None:
        return deviations
    return mock_deviations_from_seed(data_dir)
