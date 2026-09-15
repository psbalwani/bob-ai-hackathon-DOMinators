"""Deterministic rule checks: one function per deviation type.

Each function takes the protocol spec, the visit definition (the matching
entry from protocol["visit_schedule"]), and a visit record, and returns zero
or more Findings. A Finding carries enough context for severity.py to decide
severity + rationale without re-deriving anything from the raw record.

These are pure functions: no I/O, no randomness, no shared state -- so
test_rules.py can construct minimal fixtures directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Finding:
    type: str
    context: dict = field(default_factory=dict)


def _visit_def(protocol: dict, visit_id: str) -> dict:
    return next(v for v in protocol["visit_schedule"] if v["visit_id"] == visit_id)


def _is_dosing_visit(visit: dict) -> bool:
    return "dosing" in visit["required_procedures"]


def check_missed_visit(protocol: dict, record: dict) -> list[Finding]:
    if record["actual_date"] is not None:
        return []
    visit = _visit_def(protocol, record["visit_id"])
    return [Finding("missed_visit", {"is_dosing_visit": _is_dosing_visit(visit)})]


def check_late_visit(protocol: dict, record: dict) -> list[Finding]:
    if record["actual_date"] is None:
        return []  # a missed visit isn't also "late"
    visit = _visit_def(protocol, record["visit_id"])
    scheduled = date.fromisoformat(record["scheduled_date"])
    actual = date.fromisoformat(record["actual_date"])
    delta_days = (actual - scheduled).days
    window = visit["window_days"]
    if -window <= delta_days <= window:
        return []
    extra_days = abs(delta_days) - window
    return [Finding("late_visit", {"extra_days": extra_days, "window_days": window})]


def check_dosage_out_of_range(protocol: dict, record: dict) -> list[Finding]:
    dose = record.get("dosage_administered_mg")
    if dose is None:
        return []
    rules = protocol["dosing_rules"]
    if rules["min_mg"] <= dose <= rules["max_mg"]:
        return []
    return [Finding("dosage_out_of_range", {"dose": dose})]


def check_banned_comedication(protocol: dict, record: dict) -> list[Finding]:
    banned = set(protocol["banned_comedications"])
    hits = [c for c in record.get("comedications", []) if c in banned]
    if not hits:
        return []
    return [Finding("banned_comedication", {"comedications": hits})]


def check_missing_procedure(protocol: dict, record: dict) -> list[Finding]:
    if record["actual_date"] is None:
        return []  # already captured as a missed_visit; don't double-count
    visit = _visit_def(protocol, record["visit_id"])
    completed = set(record.get("procedures_completed", []))
    missing = [p for p in visit["required_procedures"] if p not in completed]
    return [Finding("missing_procedure", {"procedure": p}) for p in missing]


ALL_CHECKS = [
    check_missed_visit,
    check_late_visit,
    check_dosage_out_of_range,
    check_banned_comedication,
    check_missing_procedure,
]


def run_all_checks(protocol: dict, record: dict) -> list[Finding]:
    findings: list[Finding] = []
    for check in ALL_CHECKS:
        findings.extend(check(protocol, record))
    return findings
