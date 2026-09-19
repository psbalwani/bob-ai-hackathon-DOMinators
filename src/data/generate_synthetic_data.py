"""Synthetic dataset generator — Clinical Trial Risk Monitor & Protocol Deviation Detector.

Generates a protocol specification, site/patient registries, patient visit
records, and a ground-truth set of deliberately seeded protocol deviations,
matching the shared data contract in docs/04_data_schema.md.

This is the Track C, hour 0-4 deliverable: everything else (deviation
detection, risk scoring, CAPA generation, dashboard) builds and tests against
this dataset. No external dependencies — stdlib only, so it runs anywhere
Python 3.11+ runs.

Multi-drug portfolio: by default this generates 10 separate drug
trials/protocols sharing one physical site pool (a site can host patients
for more than one drug), not just the original single Drug X trial. The
first protocol (`TRIAL-2026-ONC-04`, "Drug X") is generated first, against
every site in the pool, and written to `--output-dir` exactly as before
(same files, same shape) so nothing that reads the default dataset needs to
change. The other 9 protocols are additional drug trials, each run against
a random subset of the same site pool, written to
`<output-dir>/drugs/<protocol_id>/` as fully self-contained dataset
directories (same file shapes as the top-level one).

Usage:
    python src/data/generate_synthetic_data.py
    python src/data/generate_synthetic_data.py --seed 7 --output-dir data/synthetic
    python src/data/generate_synthetic_data.py --num-protocols 1   # legacy single-drug dataset only
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

# --------------------------------------------------------------------------
# Protocol definition
# --------------------------------------------------------------------------

VISIT_SCHEDULE = [
    {
        "visit_id": "V1",
        "name": "Baseline",
        "scheduled_day": 0,
        "window_days": 2,
        "required_procedures": ["vitals", "blood_draw", "informed_consent"],
    },
    {
        "visit_id": "V2",
        "name": "Week 2",
        "scheduled_day": 14,
        "window_days": 3,
        "required_procedures": ["vitals", "blood_draw", "dosing"],
    },
    {
        "visit_id": "V3",
        "name": "Week 4",
        "scheduled_day": 28,
        "window_days": 3,
        "required_procedures": ["vitals", "blood_draw", "dosing"],
    },
    {
        "visit_id": "V4",
        "name": "Week 8",
        "scheduled_day": 56,
        "window_days": 5,
        "required_procedures": ["vitals", "blood_draw", "dosing", "ecg"],
    },
    {
        "visit_id": "V5",
        "name": "Week 12",
        "scheduled_day": 84,
        "window_days": 5,
        "required_procedures": ["vitals", "blood_draw", "dosing"],
    },
    {
        "visit_id": "V6",
        "name": "Week 16",
        "scheduled_day": 112,
        "window_days": 5,
        "required_procedures": ["vitals", "blood_draw", "dosing", "imaging"],
    },
    {
        "visit_id": "V7",
        "name": "End of Treatment",
        "scheduled_day": 140,
        "window_days": 7,
        "required_procedures": ["vitals", "blood_draw", "ecg", "imaging"],
    },
]

DOSING_VISIT_IDS = {v["visit_id"] for v in VISIT_SCHEDULE if "dosing" in v["required_procedures"]}

ALLOWED_COMEDICATIONS = [
    "Acetaminophen", "Ondansetron", "Loperamide", "Lisinopril",
    "Metformin", "Levothyroxine", "Omeprazole", "Atorvastatin",
]


@dataclass
class DrugConfig:
    """One drug's trial: its own protocol_id, dosing rules, and banned
    co-medication list. Everything else (visit schedule, allowed
    co-medications, deviation-injection mechanics) is shared across drugs —
    only the drug-specific facts vary, matching how src/detection/rules.py
    already reads dosing_rules/banned_comedications off the protocol dict
    rather than any hardcoded constant."""

    protocol_id: str
    drug: str
    title: str
    min_mg: float
    max_mg: float
    route: str
    banned_comedications: list[str]


# The first entry is the original single-drug trial, kept byte-for-byte
# identical to before (same protocol_id/drug/dosing/banned list) so the
# default top-level dataset (data/synthetic/protocol.json etc.) is
# unchanged for anything that only reads that one dataset.
DRUG_CONFIGS: list[DrugConfig] = [
    DrugConfig("TRIAL-2026-ONC-04", "Drug X", "Phase III Oncology Trial - Drug X",
               50, 200, "oral", ["Warfarin", "St. John's Wort", "Rifampin", "Ketoconazole"]),
    DrugConfig("TRIAL-2026-ONC-05", "Drug Y", "Phase III Oncology Trial - Drug Y",
               25, 150, "oral", ["Warfarin", "Clarithromycin", "Ritonavir"]),
    DrugConfig("TRIAL-2026-ONC-06", "Drug Z", "Phase III Oncology Trial - Drug Z",
               100, 400, "oral", ["St. John's Wort", "Rifampin", "Phenytoin"]),
    DrugConfig("TRIAL-2026-ONC-07", "Drug Alpha", "Phase III Oncology Trial - Drug Alpha",
               10, 80, "oral", ["Ketoconazole", "Itraconazole", "Warfarin"]),
    DrugConfig("TRIAL-2026-ONC-08", "Drug Beta", "Phase III Oncology Trial - Drug Beta",
               75, 300, "oral", ["Rifampin", "Carbamazepine", "St. John's Wort"]),
    DrugConfig("TRIAL-2026-ONC-09", "Drug Gamma", "Phase III Oncology Trial - Drug Gamma",
               40, 220, "oral", ["Warfarin", "Ketoconazole", "Clarithromycin"]),
    DrugConfig("TRIAL-2026-ONC-10", "Drug Delta", "Phase III Oncology Trial - Drug Delta",
               60, 250, "oral", ["Phenytoin", "Rifampin", "Ritonavir"]),
    DrugConfig("TRIAL-2026-ONC-11", "Drug Epsilon", "Phase III Oncology Trial - Drug Epsilon",
               15, 100, "oral", ["St. John's Wort", "Warfarin", "Itraconazole"]),
    DrugConfig("TRIAL-2026-ONC-12", "Drug Zeta", "Phase III Oncology Trial - Drug Zeta",
               90, 350, "oral", ["Ketoconazole", "Carbamazepine", "Rifampin"]),
    DrugConfig("TRIAL-2026-ONC-13", "Drug Theta", "Phase III Oncology Trial - Drug Theta",
               30, 180, "oral", ["Clarithromycin", "Warfarin", "Phenytoin"]),
]


def build_protocol_sections(drug: str, min_mg: float, max_mg: float, banned_comedications: list[str]) -> list[dict]:
    """Clause text a RAG layer can retrieve and cite, personalized per drug.

    Kept as an addition to the frozen Protocol Specification object (new
    field, nothing renamed/removed), so citations like "Section 4.2 -
    Prohibited Concomitant Medications" point at real text rather than
    being free-generated by an LLM. Section ids/titles/structure are
    identical across drugs (CLAUSE_FOR_TYPE below relies on that); only the
    drug name, dosing range, and banned list vary.
    """
    banned_str = ", ".join(banned_comedications)
    return [
        {
            "section_id": "3.1",
            "title": "Visit Schedule and Windows",
            "text": (
                "Section 3.1 - Visit Schedule and Windows. Each protocol visit must occur "
                "within the specified window (scheduled_day +/- window_days). Visits "
                "occurring outside this window are protocol deviations and must be "
                "recorded with the reason for the delay per ICH E6(R2) Section 4.5."
            ),
        },
        {
            "section_id": "4.1",
            "title": "Dosing Regimen",
            "text": (
                f"Section 4.1 - Dosing Regimen. {drug} is administered orally at each "
                f"dosing visit (V2-V6) within the range of {min_mg:g}mg to {max_mg:g}mg. Doses outside "
                "this range must not be administered without documented Principal "
                "Investigator (PI) approval and are otherwise a protocol deviation."
            ),
        },
        {
            "section_id": "4.2",
            "title": "Prohibited Concomitant Medications",
            "text": (
                "Section 4.2 - Prohibited Concomitant Medications. The following "
                "co-medications are prohibited for the duration of the trial due to "
                f"known CYP450 interactions with {drug}: {banned_str}. Concurrent use "
                "is a Major deviation per ICH E6(R2) Section 4.5 and must be reported "
                "to the sponsor within 24 hours of discovery."
            ),
        },
        {
            "section_id": "5.1",
            "title": "Required Procedures by Visit",
            "text": (
                "Section 5.1 - Required Procedures by Visit. Each visit has a defined "
                "set of required procedures (vitals, blood_draw, dosing, ecg, imaging, "
                "informed_consent). Missing a required procedure is a protocol "
                "deviation; severity depends on the safety/efficacy impact of the "
                "specific procedure omitted, per the site's deviation log."
            ),
        },
        {
            "section_id": "6.3",
            "title": "Protocol Deviation Reporting",
            "text": (
                "Section 6.3 - Protocol Deviation Reporting, per ICH E6(R2) Section "
                "4.5. Deviations are classified Major (affects subject safety, "
                "rights, or data integrity), Minor (limited impact, does not affect "
                "safety or primary endpoint data), or Administrative (documentation "
                "or process lapse with no safety or data impact)."
            ),
        },
    ]


# --------------------------------------------------------------------------
# Sites
# --------------------------------------------------------------------------

REGIONS = [
    ("US", "Northeast Regional Cancer Center"),
    ("US", "Midwest Oncology Partners"),
    ("US", "Pacific Coast Research Institute"),
    ("Canada", "Ontario Cancer Research Group"),
    ("Germany", "Rheinland Onkologie Zentrum"),
    ("Poland", "Warszawa Klinika Onkologiczna"),
    ("India", "Southern India Oncology Trust"),
    ("Brazil", "Instituto de Oncologia Sao Paulo"),
    ("Spain", "Centro de Oncologia Madrid"),
    ("Australia", "Sydney Cancer Trials Unit"),
]

N_SITES = 18
N_HIGH_RISK = 5
N_LOW_RISK = 5
# remaining sites are "medium" risk tier

# Fraction of sites that are high/low risk, applied when --num-sites scales
# the site count up (e.g. for the 200+-site reference-scale dataset) so the
# same "a handful of sites are clearly bad, a handful are clearly good"
# story holds at any scale -- see docs/04_data_schema.md section 6.
HIGH_RISK_FRACTION = N_HIGH_RISK / N_SITES
LOW_RISK_FRACTION = N_LOW_RISK / N_SITES

# Every non-primary drug trial runs against a random subset of the shared
# site pool (the primary drug, DRUG_CONFIGS[0], always runs against every
# site) -- this is what makes "a site can have patients for different
# drugs" real: sites overlap across trials instead of each trial getting
# its own disjoint set.
SITE_SUBSET_MIN_FRACTION = 0.5
SITE_SUBSET_MAX_FRACTION = 0.85

# --------------------------------------------------------------------------
# Data classes (mirror docs/04_data_schema.md exactly for the frozen fields)
# --------------------------------------------------------------------------


@dataclass
class Site:
    site_id: str
    site_name: str
    country: str
    activation_date: str
    # --- generation-intent metadata, NOT part of the frozen contract.
    # Track B computes the real risk_score/risk_band independently; these
    # fields only record what the generator *intended* so the seeded
    # dataset can be sanity-checked against Track B's output.
    seed_risk_tier: str  # "high" | "medium" | "low"
    seed_trend_intent: str  # "worsening" | "improving" | "stable" | "volatile"


@dataclass
class Patient:
    patient_id: str
    site_id: str
    protocol_id: str
    enrollment_date: str


@dataclass
class VisitRecord:
    visit_record_id: str
    patient_id: str
    site_id: str
    protocol_id: str
    visit_id: str
    scheduled_date: str
    actual_date: str | None
    dosage_administered_mg: float | None
    comedications: list[str]
    procedures_completed: list[str]


@dataclass
class SeededDeviation:
    """Ground-truth deviation planted by the generator.

    Field names deliberately mirror the Deviation object in
    docs/04_data_schema.md (type, protocol_clause_ref, ...) but use
    `seed_id` / `expected_severity` instead of `deviation_id` / `severity`
    so a seeded record can never collide with, or be mistaken for, a
    detector-generated `DEV-xxxxxx` record once Track A runs.
    """

    seed_id: str
    visit_record_id: str
    patient_id: str
    site_id: str
    protocol_id: str
    type: str
    expected_severity: str
    severity_rationale_hint: str
    protocol_clause_ref: str


# --------------------------------------------------------------------------
# Severity taxonomy (ICH E6(R2) Major / Minor / Administrative)
# --------------------------------------------------------------------------

# For each deviation type, the set of severities it can express and how to
# realize each one concretely (which field(s) to break and why). This is
# what lets seeded deviations skew toward Major for "high risk" sites and
# toward Administrative for "low risk" sites, instead of severity being a
# random coin flip disconnected from the site's story.

SEVERITY_RATIONALE = {
    ("banned_comedication", "Major"): (
        "Prohibited co-medication administered concurrently with the study "
        "drug; known CYP450 interaction poses a direct patient safety risk."
    ),
    ("dosage_out_of_range", "Major"): (
        "Administered dose falls outside the protocol-defined safe range "
        "without documented PI approval, directly affecting subject safety "
        "and primary efficacy data."
    ),
    ("missed_visit", "Major"): (
        "A dosing visit was missed entirely; the subject went without a "
        "scheduled administration and no safety assessment was performed."
    ),
    ("missing_procedure_consent", "Major"): (
        "Informed consent procedure is missing for the visit; a fundamental "
        "GCP/subject-rights requirement was not met."
    ),
    ("missed_visit", "Minor"): (
        "A non-dosing visit was missed; limited impact on the primary "
        "endpoint but a gap in the safety monitoring record."
    ),
    ("late_visit", "Minor"): (
        "Visit occurred outside the allowed window; no immediate safety "
        "impact but the deviation must be documented per Section 3.1."
    ),
    ("missing_procedure_data", "Minor"): (
        "A required data-collection procedure was not completed at this "
        "visit, creating a gap in the safety/efficacy dataset."
    ),
    ("late_visit", "Administrative"): (
        "Visit occurred slightly outside the allowed window; documentation "
        "lapse only, no discernible safety or data impact."
    ),
    ("missing_procedure_vitals", "Administrative"): (
        "Routine vitals were not recorded at this visit; a documentation "
        "gap with no material safety or efficacy impact."
    ),
}

CLAUSE_FOR_TYPE = {
    "banned_comedication": "Section 4.2 - Prohibited Concomitant Medications",
    "dosage_out_of_range": "Section 4.1 - Dosing Regimen",
    "missed_visit": "Section 3.1 - Visit Schedule and Windows",
    "late_visit": "Section 3.1 - Visit Schedule and Windows",
    "missing_procedure": "Section 5.1 - Required Procedures by Visit",
}

# --------------------------------------------------------------------------
# Generation helpers
# --------------------------------------------------------------------------


def build_sites(rng: random.Random, num_sites: int = N_SITES) -> list[Site]:
    if num_sites == N_SITES:
        n_high, n_low = N_HIGH_RISK, N_LOW_RISK
    else:
        n_high = max(1, round(num_sites * HIGH_RISK_FRACTION))
        n_low = max(1, round(num_sites * LOW_RISK_FRACTION))
        # leave at least one "medium" site once num_sites is large enough to
        # have one; for a tiny num_sites just cap high/low so they still fit
        n_high = min(n_high, num_sites)
        n_low = min(n_low, num_sites - n_high)

    sites: list[Site] = []
    tiers = (
        ["high"] * n_high
        + ["low"] * n_low
        + ["medium"] * (num_sites - n_high - n_low)
    )
    rng.shuffle(tiers)

    for i in range(1, num_sites + 1):
        site_id = f"SITE-{i:03d}"
        country, base_name = REGIONS[(i - 1) % len(REGIONS)]
        tier = tiers[i - 1]
        if tier == "high":
            trend_intent = rng.choice(["worsening", "worsening", "volatile"])
        elif tier == "low":
            trend_intent = rng.choice(["improving", "stable"])
        else:
            trend_intent = "stable"

        activation = date(2025, 11, 1) + timedelta(days=rng.randint(0, 60))
        sites.append(
            Site(
                site_id=site_id,
                site_name=f"Site {i:03d} - {base_name}",
                country=country,
                activation_date=activation.isoformat(),
                seed_risk_tier=tier,
                seed_trend_intent=trend_intent,
            )
        )
    return sites


def pick_site_subset(rng: random.Random, sites: list[Site]) -> list[Site]:
    """A random subset of the shared site pool for one non-primary drug
    trial, so sites overlap across trials instead of partitioning them."""
    frac = rng.uniform(SITE_SUBSET_MIN_FRACTION, SITE_SUBSET_MAX_FRACTION)
    n = max(3, round(len(sites) * frac))
    n = min(n, len(sites))
    return sorted(rng.sample(sites, n), key=lambda s: s.site_id)


def build_patients(
    rng: random.Random,
    sites: list[Site],
    min_per_site: int,
    max_per_site: int,
    protocol_id: str,
    start_counter: int = 1,
) -> tuple[list[Patient], int]:
    patients: list[Patient] = []
    counter = start_counter
    for site in sites:
        n = rng.randint(min_per_site, max_per_site)
        for _ in range(n):
            enrollment = date(2025, 12, 1) + timedelta(days=rng.randint(0, 150))
            patients.append(
                Patient(
                    patient_id=f"PT-{counter:05d}",
                    site_id=site.site_id,
                    protocol_id=protocol_id,
                    enrollment_date=enrollment.isoformat(),
                )
            )
            counter += 1
    return patients, counter


def build_clean_visit_records(
    rng: random.Random,
    patients: list[Patient],
    protocol_id: str,
    min_mg: float,
    max_mg: float,
    start_counter: int = 1,
) -> tuple[list[VisitRecord], int]:
    """Every patient x every scheduled visit, fully protocol-compliant.

    Deviations are injected afterward by `inject_deviations`, so at this
    stage every record is "clean" -- this keeps the seeded deviation set
    the *only* true positives in the dataset, which is what makes the
    detector's recall/precision metrics in docs/01_project_planning.md
    meaningful.
    """
    records: list[VisitRecord] = []
    counter = start_counter
    for patient in patients:
        enrollment = date.fromisoformat(patient.enrollment_date)
        for visit in VISIT_SCHEDULE:
            scheduled = enrollment + timedelta(days=visit["scheduled_day"])
            actual = scheduled + timedelta(days=rng.randint(-1, max(1, visit["window_days"] - 1)))

            dosage = None
            if visit["visit_id"] in DOSING_VISIT_IDS:
                dosage = float(rng.randint(int(min_mg), int(max_mg)))

            comeds: list[str] = []
            if rng.random() < 0.15:
                comeds = [rng.choice(ALLOWED_COMEDICATIONS)]

            records.append(
                VisitRecord(
                    visit_record_id=f"REC-{counter:06d}",
                    patient_id=patient.patient_id,
                    site_id=patient.site_id,
                    protocol_id=protocol_id,
                    visit_id=visit["visit_id"],
                    scheduled_date=scheduled.isoformat(),
                    actual_date=actual.isoformat(),
                    dosage_administered_mg=dosage,
                    comedications=comeds,
                    procedures_completed=list(visit["required_procedures"]),
                )
            )
            counter += 1
    return records, counter


def visit_def(visit_id: str) -> dict:
    return next(v for v in VISIT_SCHEDULE if v["visit_id"] == visit_id)


def inject_deviations(
    rng: random.Random,
    sites: list[Site],
    records: list[VisitRecord],
    counts_by_tier: dict[str, tuple[int, int]],
    banned_comedications: list[str],
    start_seed_counter: int = 1,
) -> tuple[list[SeededDeviation], int]:
    """Mutate a subset of `records` in place to encode a real deviation, and
    return the matching ground-truth SeededDeviation list.

    Deviation volume and severity mix are driven by each site's
    `seed_risk_tier` so the dataset tells a coherent risk story: high-risk
    sites cluster frequent, severe deviations (optionally recency-weighted
    for a "worsening" trend); low-risk sites have few, mild ones.
    """
    records_by_site: dict[str, list[VisitRecord]] = {}
    for r in records:
        records_by_site.setdefault(r.site_id, []).append(r)

    severity_mix = {
        "high": ["Major", "Major", "Major", "Minor", "Minor", "Administrative"],
        "medium": ["Major", "Minor", "Minor", "Minor", "Administrative", "Administrative"],
        "low": ["Minor", "Administrative", "Administrative", "Administrative"],
    }

    seeded: list[SeededDeviation] = []
    seed_counter = start_seed_counter

    for site in sites:
        site_records = records_by_site.get(site.site_id)
        if not site_records:
            continue
        lo, hi = counts_by_tier[site.seed_risk_tier]
        n_deviations = rng.randint(lo, hi)
        if n_deviations == 0:
            continue

        # Recency weighting for a "worsening" story: bias sampling toward
        # later visits (V5-V7) for this site's patients.
        if site.seed_trend_intent == "worsening":
            weights = [3 if r.visit_id in {"V5", "V6", "V7"} else 1 for r in site_records]
        elif site.seed_trend_intent == "improving":
            weights = [3 if r.visit_id in {"V1", "V2", "V3"} else 1 for r in site_records]
        else:
            weights = [1 for _ in site_records]

        n_deviations = min(n_deviations, len(site_records))
        chosen = rng.choices(site_records, weights=weights, k=n_deviations)
        # de-dupe while preserving order (a record should only carry one
        # seeded deviation, to keep the ground-truth set unambiguous)
        seen_ids: set[str] = set()
        unique_chosen = []
        for r in chosen:
            if r.visit_record_id not in seen_ids:
                seen_ids.add(r.visit_record_id)
                unique_chosen.append(r)

        for record in unique_chosen:
            target_severity = rng.choice(severity_mix[site.seed_risk_tier])
            dev_type, expected_severity, rationale, clause = _apply_deviation(
                rng, record, target_severity, banned_comedications
            )
            if dev_type is None:
                continue  # visit shape couldn't support the requested severity/type

            seeded.append(
                SeededDeviation(
                    seed_id=f"SEED-{seed_counter:06d}",
                    visit_record_id=record.visit_record_id,
                    patient_id=record.patient_id,
                    site_id=record.site_id,
                    protocol_id=record.protocol_id,
                    type=dev_type,
                    expected_severity=expected_severity,
                    severity_rationale_hint=rationale,
                    protocol_clause_ref=clause,
                )
            )
            seed_counter += 1

    return seeded, seed_counter


def _apply_deviation(rng: random.Random, record: VisitRecord, target_severity: str, banned_comedications: list[str]):
    """Mutate `record` to realize one deviation matching `target_severity`.

    Returns (type, expected_severity, rationale, protocol_clause_ref), or
    (None, None, None, None) if this visit shape can't express that
    severity (caller skips it).
    """
    visit = visit_def(record.visit_id)
    is_dosing_visit = record.visit_id in DOSING_VISIT_IDS

    if target_severity == "Major":
        options = ["banned_comedication", "dosage_out_of_range"]
        if is_dosing_visit:
            options.append("missed_visit")
        if record.visit_id == "V1":
            options.append("missing_procedure_consent")
        choice = rng.choice(options)

        if choice == "banned_comedication":
            record.comedications = [rng.choice(banned_comedications)]
            return (
                "banned_comedication", "Major",
                SEVERITY_RATIONALE[("banned_comedication", "Major")],
                CLAUSE_FOR_TYPE["banned_comedication"],
            )
        if choice == "dosage_out_of_range" and is_dosing_visit:
            record.dosage_administered_mg = float(
                rng.choice([rng.randint(10, 45), rng.randint(210, 260)])
            )
            return (
                "dosage_out_of_range", "Major",
                SEVERITY_RATIONALE[("dosage_out_of_range", "Major")],
                CLAUSE_FOR_TYPE["dosage_out_of_range"],
            )
        if choice == "missed_visit":
            record.actual_date = None
            record.dosage_administered_mg = None
            record.comedications = []
            record.procedures_completed = []
            return (
                "missed_visit", "Major",
                SEVERITY_RATIONALE[("missed_visit", "Major")],
                CLAUSE_FOR_TYPE["missed_visit"],
            )
        if choice == "missing_procedure_consent":
            record.procedures_completed = [
                p for p in record.procedures_completed if p != "informed_consent"
            ]
            return (
                "missing_procedure", "Major",
                SEVERITY_RATIONALE[("missing_procedure_consent", "Major")],
                CLAUSE_FOR_TYPE["missing_procedure"],
            )
        return (None, None, None, None)

    if target_severity == "Minor":
        options = ["late_visit"]
        if not is_dosing_visit:
            options.append("missed_visit")
        data_procs = [p for p in visit["required_procedures"] if p not in ("vitals", "dosing")]
        if data_procs:
            options.append("missing_procedure_data")
        choice = rng.choice(options)

        if choice == "late_visit":
            scheduled = date.fromisoformat(record.scheduled_date)
            late_by = visit["window_days"] + rng.randint(2, 10)
            record.actual_date = (scheduled + timedelta(days=late_by)).isoformat()
            return (
                "late_visit", "Minor",
                SEVERITY_RATIONALE[("late_visit", "Minor")],
                CLAUSE_FOR_TYPE["late_visit"],
            )
        if choice == "missed_visit":
            record.actual_date = None
            record.dosage_administered_mg = None
            record.comedications = []
            record.procedures_completed = []
            return (
                "missed_visit", "Minor",
                SEVERITY_RATIONALE[("missed_visit", "Minor")],
                CLAUSE_FOR_TYPE["missed_visit"],
            )
        if choice == "missing_procedure_data" and data_procs:
            dropped = rng.choice(data_procs)
            record.procedures_completed = [
                p for p in record.procedures_completed if p != dropped
            ]
            return (
                "missing_procedure", "Minor",
                SEVERITY_RATIONALE[("missing_procedure_data", "Minor")],
                CLAUSE_FOR_TYPE["missing_procedure"],
            )
        return (None, None, None, None)

    # Administrative
    options = ["late_visit"]
    if "vitals" in visit["required_procedures"]:
        options.append("missing_procedure_vitals")
    choice = rng.choice(options)

    if choice == "late_visit":
        scheduled = date.fromisoformat(record.scheduled_date)
        late_by = visit["window_days"] + rng.randint(1, 2)
        record.actual_date = (scheduled + timedelta(days=late_by)).isoformat()
        return (
            "late_visit", "Administrative",
            SEVERITY_RATIONALE[("late_visit", "Administrative")],
            CLAUSE_FOR_TYPE["late_visit"],
        )
    if choice == "missing_procedure_vitals":
        record.procedures_completed = [
            p for p in record.procedures_completed if p != "vitals"
        ]
        return (
            "missing_procedure", "Administrative",
            SEVERITY_RATIONALE[("missing_procedure_vitals", "Administrative")],
            CLAUSE_FOR_TYPE["missing_procedure"],
        )
    return (None, None, None, None)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            row = dict(row)
            for key in ("comedications", "procedures_completed"):
                if key in row and isinstance(row[key], list):
                    row[key] = "|".join(row[key])
            writer.writerow(row)


def write_summary(
    path: Path,
    protocol_id: str,
    sites: list[Site],
    patients: list[Patient],
    records: list[VisitRecord],
    deviations: list[SeededDeviation],
) -> None:
    by_type: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    by_site: dict[str, int] = {}
    for d in deviations:
        by_type[d.type] = by_type.get(d.type, 0) + 1
        by_severity[d.expected_severity] = by_severity.get(d.expected_severity, 0) + 1
        by_site[d.site_id] = by_site.get(d.site_id, 0) + 1

    site_by_id = {s.site_id: s for s in sites}
    lines = [
        "# Synthetic Dataset Summary",
        "",
        f"- Protocol: `{protocol_id}`",
        f"- Sites: {len(sites)}",
        f"- Patients: {len(patients)}",
        f"- Visit records: {len(records)}",
        f"- Seeded deviations (ground truth): {len(deviations)}",
        "",
        "## Deviations by type",
        "",
    ]
    for k, v in sorted(by_type.items()):
        lines.append(f"- `{k}`: {v}")
    lines += ["", "## Deviations by severity", ""]
    for k in ("Major", "Minor", "Administrative"):
        lines.append(f"- {k}: {by_severity.get(k, 0)}")

    lines += ["", "## Sites, ranked by seeded deviation count", ""]
    lines.append("| site_id | seed_risk_tier | seed_trend_intent | seeded_deviations |")
    lines.append("|---|---|---|---|")
    for site_id, count in sorted(by_site.items(), key=lambda kv: -kv[1]):
        s = site_by_id[site_id]
        lines.append(f"| {site_id} | {s.seed_risk_tier} | {s.seed_trend_intent} | {count} |")
    # include zero-deviation sites too
    for s in sites:
        if s.site_id not in by_site:
            lines.append(f"| {s.site_id} | {s.seed_risk_tier} | {s.seed_trend_intent} | 0 |")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _generate_one_protocol(
    rng: random.Random,
    cfg: DrugConfig,
    sites: list[Site],
    args,
    patient_counter: int,
    record_counter: int,
    seed_counter: int,
) -> tuple[dict, list[Patient], list[VisitRecord], list[SeededDeviation], int, int, int]:
    """Generate one drug trial's patients/visits/deviations against `sites`
    (already the right subset for this drug). Counters are threaded through
    and returned so patient/visit/seed IDs stay globally unique across every
    protocol in one run, not just within a single protocol."""
    patients, patient_counter = build_patients(
        rng, sites, args.min_patients_per_site, args.max_patients_per_site, cfg.protocol_id, patient_counter
    )
    records, record_counter = build_clean_visit_records(
        rng, patients, cfg.protocol_id, cfg.min_mg, cfg.max_mg, record_counter
    )
    deviations, seed_counter = inject_deviations(
        rng, sites, records,
        counts_by_tier={"high": (6, 10), "medium": (1, 3), "low": (0, 1)},
        banned_comedications=cfg.banned_comedications,
        start_seed_counter=seed_counter,
    )

    protocol = {
        "protocol_id": cfg.protocol_id,
        "title": cfg.title,
        "visit_schedule": VISIT_SCHEDULE,
        "dosing_rules": {"drug": cfg.drug, "min_mg": cfg.min_mg, "max_mg": cfg.max_mg, "route": cfg.route},
        "banned_comedications": cfg.banned_comedications,
        "ich_gcp_version": "E6(R2)",
        "protocol_sections": build_protocol_sections(cfg.drug, cfg.min_mg, cfg.max_mg, cfg.banned_comedications),
    }
    return protocol, patients, records, deviations, patient_counter, record_counter, seed_counter


def _write_dataset_dir(
    out_dir: Path,
    protocol: dict,
    sites: list[Site],
    patients: list[Patient],
    records: list[VisitRecord],
    deviations: list[SeededDeviation],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "protocol.json", protocol)
    write_json(out_dir / "sites.json", [asdict(s) for s in sites])
    write_json(out_dir / "patients.json", [asdict(p) for p in patients])
    write_json(out_dir / "visit_records.json", [asdict(r) for r in records])
    write_json(out_dir / "seeded_deviations_ground_truth.json", [asdict(d) for d in deviations])

    write_csv(
        out_dir / "visit_records.csv", [asdict(r) for r in records],
        fieldnames=list(VisitRecord.__annotations__.keys()),
    )
    write_csv(
        out_dir / "seeded_deviations_ground_truth.csv", [asdict(d) for d in deviations],
        fieldnames=list(SeededDeviation.__annotations__.keys()),
    )

    write_summary(out_dir / "dataset_summary.md", protocol["protocol_id"], sites, patients, records, deviations)


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42, reproducible)")
    parser.add_argument(
        "--output-dir", type=Path, default=Path("data/synthetic"),
        help="Output directory (default: data/synthetic)",
    )
    parser.add_argument(
        "--num-sites", type=int, default=N_SITES,
        help=f"Number of sites (default: {N_SITES}, demo scale). Use e.g. 220 for the "
             "5,000+ visits / 200+ sites reference scale named in docs/01_project_planning.md "
             "-- high/low risk tiers scale proportionally so the same risk story still holds.",
    )
    parser.add_argument("--min-patients-per-site", type=int, default=12)
    parser.add_argument("--max-patients-per-site", type=int, default=20)
    parser.add_argument(
        "--num-protocols", type=int, default=len(DRUG_CONFIGS),
        help=f"Number of drug trials to generate (default: {len(DRUG_CONFIGS)}, max {len(DRUG_CONFIGS)}). "
             "The first is always the original single-drug trial, written to --output-dir exactly as "
             "before; use 1 to reproduce the legacy single-drug dataset with no multi-drug siblings.",
    )
    args = parser.parse_args()

    num_protocols = max(1, min(args.num_protocols, len(DRUG_CONFIGS)))
    configs = DRUG_CONFIGS[:num_protocols]

    rng = random.Random(args.seed)
    out_dir: Path = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # Shared site pool, generated once. The primary drug (configs[0]) always
    # runs against every site in the pool -- generated first, with the exact
    # same call sequence as the original single-drug generator, so the
    # top-level dataset is unchanged when num_protocols == 1.
    sites = build_sites(rng, args.num_sites)

    patient_counter = 1
    record_counter = 1
    seed_counter = 1

    primary_protocol, primary_patients, primary_records, primary_deviations, patient_counter, record_counter, seed_counter = (
        _generate_one_protocol(rng, configs[0], sites, args, patient_counter, record_counter, seed_counter)
    )
    _write_dataset_dir(out_dir, primary_protocol, sites, primary_patients, primary_records, primary_deviations)

    print(f"Generated dataset in {out_dir.resolve()}")
    print(f"  protocol:   {primary_protocol['protocol_id']} ({primary_protocol['dosing_rules']['drug']})")
    print(f"  sites:      {len(sites)}")
    print(f"  patients:   {len(primary_patients)}")
    print(f"  visits:     {len(primary_records)}")
    print(f"  deviations: {len(primary_deviations)} (seed={args.seed})")

    for cfg in configs[1:]:
        site_subset = pick_site_subset(rng, sites)
        protocol, patients, records, deviations, patient_counter, record_counter, seed_counter = (
            _generate_one_protocol(rng, cfg, site_subset, args, patient_counter, record_counter, seed_counter)
        )
        drug_dir = out_dir / "drugs" / cfg.protocol_id
        _write_dataset_dir(drug_dir, protocol, site_subset, patients, records, deviations)
        print(f"  + {cfg.protocol_id} ({cfg.drug}): {len(site_subset)} sites, {len(patients)} patients, "
              f"{len(records)} visits, {len(deviations)} deviations -> {drug_dir}")

    if num_protocols > 1:
        all_site_ids_used: dict[str, int] = {}
        for cfg in configs:
            cfg_dir = out_dir if cfg is configs[0] else out_dir / "drugs" / cfg.protocol_id
            cfg_sites = json.loads((cfg_dir / "sites.json").read_text(encoding="utf-8"))
            for s in cfg_sites:
                all_site_ids_used[s["site_id"]] = all_site_ids_used.get(s["site_id"], 0) + 1
        shared = sum(1 for count in all_site_ids_used.values() if count > 1)
        print(f"\n{num_protocols} protocols generated; {shared}/{len(sites)} sites shared across more than one protocol.")


if __name__ == "__main__":
    main()
