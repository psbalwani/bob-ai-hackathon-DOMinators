"""Unit tests for src/detection/rules.py -- constructed minimal fixtures,
covering boundary cases explicitly."""

from src.detection.rules import (
    check_banned_comedication,
    check_dosage_out_of_range,
    check_late_visit,
    check_missed_visit,
    check_missing_procedure,
)

PROTOCOL = {
    "visit_schedule": [
        {
            "visit_id": "V1",
            "scheduled_day": 0,
            "window_days": 2,
            "required_procedures": ["vitals", "blood_draw", "informed_consent"],
        },
        {
            "visit_id": "V2",
            "scheduled_day": 14,
            "window_days": 3,
            "required_procedures": ["vitals", "blood_draw", "dosing"],
        },
    ],
    "dosing_rules": {"drug": "Drug X", "min_mg": 50, "max_mg": 200, "route": "oral"},
    "banned_comedications": ["Warfarin", "St. John's Wort"],
}


def make_record(**overrides) -> dict:
    record = {
        "visit_record_id": "REC-000001",
        "patient_id": "PT-00001",
        "site_id": "SITE-001",
        "protocol_id": "TRIAL-2026-ONC-04",
        "visit_id": "V2",
        "scheduled_date": "2026-01-15",
        "actual_date": "2026-01-15",
        "dosage_administered_mg": 100.0,
        "comedications": [],
        "procedures_completed": ["vitals", "blood_draw", "dosing"],
    }
    record.update(overrides)
    return record


def test_missed_visit_on_dosing_visit_flags():
    record = make_record(actual_date=None, dosage_administered_mg=None, procedures_completed=[])
    findings = check_missed_visit(PROTOCOL, record)
    assert len(findings) == 1
    assert findings[0].type == "missed_visit"
    assert findings[0].context["is_dosing_visit"] is True


def test_missed_visit_on_non_dosing_visit():
    record = make_record(
        visit_id="V1", scheduled_date="2026-01-01", actual_date=None, procedures_completed=[]
    )
    findings = check_missed_visit(PROTOCOL, record)
    assert findings[0].context["is_dosing_visit"] is False


def test_present_visit_is_not_missed():
    assert check_missed_visit(PROTOCOL, make_record()) == []


def test_late_visit_within_window_is_clean():
    # V2 window is +/-3 days; day 16 is +2, inside the window.
    record = make_record(scheduled_date="2026-01-14", actual_date="2026-01-16")
    assert check_late_visit(PROTOCOL, record) == []


def test_late_visit_exactly_at_window_edge_is_clean():
    record = make_record(scheduled_date="2026-01-14", actual_date="2026-01-17")  # +3, edge
    assert check_late_visit(PROTOCOL, record) == []


def test_late_visit_one_day_past_window():
    record = make_record(scheduled_date="2026-01-14", actual_date="2026-01-18")  # +4 = 1 extra day
    findings = check_late_visit(PROTOCOL, record)
    assert len(findings) == 1
    assert findings[0].context["extra_days"] == 1


def test_late_visit_deep_past_window():
    record = make_record(scheduled_date="2026-01-14", actual_date="2026-01-27")  # +13 = 10 extra
    findings = check_late_visit(PROTOCOL, record)
    assert findings[0].context["extra_days"] == 10


def test_missed_visit_is_not_also_late():
    record = make_record(actual_date=None)
    assert check_late_visit(PROTOCOL, record) == []


def test_dosage_within_range_is_clean():
    assert check_dosage_out_of_range(PROTOCOL, make_record(dosage_administered_mg=50.0)) == []
    assert check_dosage_out_of_range(PROTOCOL, make_record(dosage_administered_mg=200.0)) == []


def test_dosage_below_min_flags():
    findings = check_dosage_out_of_range(PROTOCOL, make_record(dosage_administered_mg=49.0))
    assert findings[0].type == "dosage_out_of_range"


def test_dosage_above_max_flags():
    findings = check_dosage_out_of_range(PROTOCOL, make_record(dosage_administered_mg=201.0))
    assert findings[0].type == "dosage_out_of_range"


def test_dosage_none_is_clean():
    assert check_dosage_out_of_range(PROTOCOL, make_record(dosage_administered_mg=None)) == []


def test_banned_comedication_flags():
    findings = check_banned_comedication(PROTOCOL, make_record(comedications=["Warfarin"]))
    assert findings[0].type == "banned_comedication"
    assert findings[0].context["comedications"] == ["Warfarin"]


def test_allowed_comedication_is_clean():
    assert check_banned_comedication(PROTOCOL, make_record(comedications=["Metformin"])) == []


def test_missing_procedure_flags_each_missing_one():
    record = make_record(procedures_completed=["vitals"])
    findings = check_missing_procedure(PROTOCOL, record)
    types = {f.context["procedure"] for f in findings}
    assert types == {"blood_draw", "dosing"}


def test_no_missing_procedure_when_all_completed():
    assert check_missing_procedure(PROTOCOL, make_record()) == []


def test_missing_procedure_skipped_when_visit_missed():
    record = make_record(actual_date=None, procedures_completed=[])
    assert check_missing_procedure(PROTOCOL, record) == []
