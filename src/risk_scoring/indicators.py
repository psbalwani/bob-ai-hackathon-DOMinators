"""Raw leading-indicator computations for site risk scoring.

Each function returns a value in [0, 1] for one site. See DESIGN.md for the
definitions and why each indicator is normalized/capped the way it is.
"""

from __future__ import annotations

from datetime import date, datetime
from statistics import median

SEVERITY_POINTS = {"Major": 1.0, "Minor": 0.4, "Administrative": 0.1}

# Caps: the raw ratio at which an indicator maxes out at 1.0. Calibrated to
# the realistic worst-case range for a trial at this project's documented
# scale (docs/04_data_schema.md section 6: ~250-300 patients, 40-60 seeded
# deviations) — not to an abstract ceiling. See DESIGN.md.
SEVERITY_MIX_CAP = 0.08
FREQUENCY_CAP = 0.10
RECENCY_CAP = 0.01
RECENCY_HALF_LIFE_DAYS = 30
TREND_SCALE = 0.15


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def severity_mix_weight(site_deviations: list[dict], total_visits: int) -> float:
    if total_visits == 0:
        return 0.0
    points = sum(SEVERITY_POINTS.get(d["severity"], 0.0) for d in site_deviations)
    raw = points / total_visits
    return min(raw / SEVERITY_MIX_CAP, 1.0)


def deviation_frequency(site_deviations: list[dict], total_visits: int) -> float:
    if total_visits == 0:
        return 0.0
    raw = len(site_deviations) / total_visits
    return min(raw / FREQUENCY_CAP, 1.0)


def repeat_offense_rate(site_deviations: list[dict]) -> float:
    counts: dict[str, int] = {}
    for d in site_deviations:
        counts[d["patient_id"]] = counts.get(d["patient_id"], 0) + 1
    patients_with_1plus = len(counts)
    if patients_with_1plus == 0:
        return 0.0
    patients_with_2plus = sum(1 for c in counts.values() if c >= 2)
    return patients_with_2plus / patients_with_1plus


def recency_weight(site_deviations: list[dict], total_visits: int, as_of: date) -> float:
    if total_visits == 0:
        return 0.0
    total = 0.0
    for d in site_deviations:
        detected = _parse_date(d.get("detected_at"))
        if detected is None:
            continue
        days_since = max((as_of - detected).days, 0)
        total += 0.5 ** (days_since / RECENCY_HALF_LIFE_DAYS)
    raw = total / total_visits
    return min(raw / RECENCY_CAP, 1.0)


def _early_late_split_day(visit_schedule: list[dict]) -> int:
    return int(median(v["scheduled_day"] for v in visit_schedule))


def trend_slope(
    site_deviations: list[dict],
    site_visit_records: list[dict],
    visit_schedule: list[dict],
) -> tuple[float, float]:
    """Returns (raw_signed in [-1, 1], scored_raw in [0, 1]).

    raw_signed > 0 means worsening (more deviations in the back half of the
    trial timeline), < 0 means improving. scored_raw is the same signal
    rescaled to [0, 1] for use as a scoring-model indicator (0.5 = flat).
    """
    split_day = _early_late_split_day(visit_schedule)
    day_by_visit_id = {v["visit_id"]: v["scheduled_day"] for v in visit_schedule}

    early_visits = late_visits = 0
    for v in site_visit_records:
        day = day_by_visit_id.get(v["visit_id"])
        if day is None:
            continue
        if day < split_day:
            early_visits += 1
        else:
            late_visits += 1

    early_devs = late_devs = 0
    visit_lookup = {v["visit_record_id"]: v for v in site_visit_records}
    for d in site_deviations:
        v = visit_lookup.get(d["visit_record_id"])
        if v is None:
            continue
        day = day_by_visit_id.get(v["visit_id"])
        if day is None:
            continue
        if day < split_day:
            early_devs += 1
        else:
            late_devs += 1

    early_rate = early_devs / early_visits if early_visits else 0.0
    late_rate = late_devs / late_visits if late_visits else 0.0

    raw_signed = max(min((late_rate - early_rate) / TREND_SCALE, 1.0), -1.0)
    scored_raw = (raw_signed + 1) / 2
    return raw_signed, scored_raw
