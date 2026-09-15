"""Data loading for Track B.

`load_deviations` picks the best available source of real, Deviation-shaped
dicts (docs/04_data_schema.md section 3), in order:

1. An explicit `deviations` argument (tests, callers that already have them).
2. Track A's real detector snapshot, if `src/detection/store.py` has written
   one for this data_dir (see `_detected_snapshot_path` below) --
   `data/synthetic` -> `data/detected/deviations.json`,
   `data/synthetic_fullscale` -> `data/detected_fullscale/deviations.json`.
   Produced by running Track A's detector once, e.g. via its FastAPI
   service's startup hook, or `src.detection.detector.detect_deviations`
   directly against a given data dir.
3. `mock_deviations_from_seed`, adapting Track C's ground-truth seed file
   (`seeded_deviations_ground_truth.json`) into the same shape -- the
   original fallback per the team-division note ("can build against mocked
   deviations until Track A is ready"), now only used if neither of the
   above is available (e.g. a fresh checkout before anyone has run Track A).
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


def _detected_snapshot_path(data_dir: Path) -> Path:
    """Where Track A's detector snapshot would live for this data_dir.

    Mirrors src/detection/store.py's DEFAULT_SNAPSHOT_PATH convention
    (data/detected/deviations.json) but derives the sibling directory name
    from data_dir so a full-scale run (data/synthetic_fullscale) looks for
    its own snapshot (data/detected_fullscale) rather than the demo one.
    """
    detected_dir_name = data_dir.name.replace("synthetic", "detected")
    return data_dir.parent / detected_dir_name / "deviations.json"


def load_real_deviations_snapshot(data_dir: Path) -> list[dict] | None:
    """Track A's real detector output for this data_dir, if it's been run."""
    path = _detected_snapshot_path(data_dir)
    if not path.exists():
        return None
    return _load_json(path)


def load_deviations(data_dir: Path, deviations: list[dict] | None = None) -> list[dict]:
    """Return Deviation-shaped dicts: explicit override > Track A's real
    detector snapshot > the mock adapter, in that order (see module
    docstring)."""
    if deviations is not None:
        return deviations
    real = load_real_deviations_snapshot(data_dir)
    if real is not None:
        return real
    return mock_deviations_from_seed(data_dir)
