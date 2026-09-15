"""In-memory CAPA report store, keyed by capa_id, with a JSON snapshot on
disk so Track D can integrate against a static file if the API isn't
running -- same pattern as src/detection/store.py.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import CapaReport

DEFAULT_SNAPSHOT_PATH = Path("data/capa/reports.json")

_by_id: dict[str, CapaReport] = {}
_counter = 0


def clear() -> None:
    global _counter
    _by_id.clear()
    _counter = 0


def next_capa_id() -> str:
    global _counter
    _counter += 1
    return f"CAPA-{_counter:06d}"


def save(report: CapaReport) -> None:
    _by_id[report.capa_id] = report


def get(capa_id: str) -> CapaReport | None:
    return _by_id.get(capa_id)


def all_reports() -> list[CapaReport]:
    return list(_by_id.values())


def save_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([r.to_dict() for r in all_reports()], indent=2),
        encoding="utf-8",
    )
