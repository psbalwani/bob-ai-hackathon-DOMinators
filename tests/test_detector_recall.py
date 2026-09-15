"""Integration test: run the real detector over the real synthetic dataset
and score it against the seeded ground truth.

Requires data/synthetic/ to exist -- run
`python src/data/generate_synthetic_data.py` first if these are skipped.
"""

import json
from pathlib import Path

import pytest

from src.detection.detector import detect_deviations

SYNTHETIC_DIR = Path("data/synthetic")

pytestmark = pytest.mark.skipif(
    not (SYNTHETIC_DIR / "protocol.json").exists(),
    reason="data/synthetic/ not generated -- run src/data/generate_synthetic_data.py first",
)


@pytest.fixture(scope="module")
def dataset():
    protocol = json.loads((SYNTHETIC_DIR / "protocol.json").read_text(encoding="utf-8"))
    visit_records = json.loads((SYNTHETIC_DIR / "visit_records.json").read_text(encoding="utf-8"))
    ground_truth = json.loads(
        (SYNTHETIC_DIR / "seeded_deviations_ground_truth.json").read_text(encoding="utf-8")
    )
    return protocol, visit_records, ground_truth


@pytest.fixture(scope="module")
def detected(dataset):
    protocol, visit_records, _ = dataset
    return detect_deviations(protocol, visit_records)


def test_recall_against_seeded_ground_truth(dataset, detected):
    _, _, ground_truth = dataset
    detected_keys = {(d.visit_record_id, d.type) for d in detected}

    hits = 0
    misses = []
    for seed in ground_truth:
        key = (seed["visit_record_id"], seed["type"])
        if key in detected_keys:
            hits += 1
        else:
            misses.append(seed["seed_id"])

    recall = hits / len(ground_truth)
    print(f"\nRecall: {hits}/{len(ground_truth)} = {recall:.1%}; missed: {misses}")
    assert recall >= 0.95, f"recall {recall:.1%} below 95% target; missed {misses}"


def test_no_false_positives_on_clean_records(dataset, detected):
    _, _, ground_truth = dataset
    seeded_record_ids = {seed["visit_record_id"] for seed in ground_truth}

    false_positives = [d for d in detected if d.visit_record_id not in seeded_record_ids]
    print(f"\nFalse positives: {len(false_positives)}")
    assert not false_positives, (
        f"detector flagged {len(false_positives)} clean records: "
        f"{[(d.visit_record_id, d.type) for d in false_positives[:10]]}"
    )


def test_severity_agreement_with_expected_severity(dataset, detected):
    _, _, ground_truth = dataset
    detected_by_key = {(d.visit_record_id, d.type): d for d in detected}

    matched = 0
    agreed = 0
    disagreements = []
    for seed in ground_truth:
        key = (seed["visit_record_id"], seed["type"])
        if key not in detected_by_key:
            continue
        matched += 1
        detected_dev = detected_by_key[key]
        if detected_dev.severity == seed["expected_severity"]:
            agreed += 1
        else:
            disagreements.append(
                (seed["seed_id"], seed["expected_severity"], detected_dev.severity)
            )

    agreement = agreed / matched
    print(f"\nSeverity agreement: {agreed}/{matched} = {agreement:.1%}; disagreements: {disagreements}")
    assert agreement >= 0.85, f"severity agreement {agreement:.1%} below 85% target"
