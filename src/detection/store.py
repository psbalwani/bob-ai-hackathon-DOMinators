"""In-memory deviation store, keyed by site_id, with a JSON snapshot on disk
so Track B/C/D can integrate against a static file if the API isn't running.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Deviation

DEFAULT_SNAPSHOT_PATH = Path("data/detected/deviations.json")

_by_site: dict[str, list[Deviation]] = {}


def clear() -> None:
    _by_site.clear()


def replace_all(deviations: list[Deviation]) -> None:
    """Replace the entire store with a fresh detection run's output."""
    clear()
    for d in deviations:
        _by_site.setdefault(d.site_id, []).append(d)


def replace_for_records(deviations: list[Deviation], considered_record_ids: set[str]) -> None:
    """Merge a detection run's output covering only `considered_record_ids`.

    Drops any previously stored deviation for one of those record ids (so a
    re-run doesn't duplicate or leave stale results), keeps everything else
    untouched, then appends the fresh deviations.
    """
    for site_id in list(_by_site.keys()):
        kept = [d for d in _by_site[site_id] if d.visit_record_id not in considered_record_ids]
        if kept:
            _by_site[site_id] = kept
        else:
            del _by_site[site_id]
    for d in deviations:
        _by_site.setdefault(d.site_id, []).append(d)


def for_site(site_id: str) -> list[Deviation] | None:
    return _by_site.get(site_id)


def known_sites() -> list[str]:
    return list(_by_site.keys())


def all_deviations() -> list[Deviation]:
    return [d for devs in _by_site.values() for d in devs]


def save_snapshot(path: Path = DEFAULT_SNAPSHOT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([d.to_dict() for d in all_deviations()], indent=2),
        encoding="utf-8",
    )
