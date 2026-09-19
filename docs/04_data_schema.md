# Data Schema — Shared Contract

This is the shared source of truth for data shapes across all four tracks. **Freeze this in the first 2 hours.** Any change after that must be flagged to the whole team before merging.

Since real patient data cannot and should not be used, the team will generate a **synthetic dataset** matching this schema (Track C, hour 0–4 priority).

**Post-freeze addition (multi-drug):** the platform now serves 10 separate drug trials (protocols), not just one. Every object below still has exactly one `protocol_id` and belongs to exactly one protocol — nothing about a single object's shape changed. What's new: (1) sites are shared across protocols (a `site_id` can appear under more than one protocol, with independent patients/visits/deviations/risk scores per protocol), and (2) `CapaReport` (section 5) gained an additive `protocol_id` field so a CAPA report on a shared site can be attributed to the right drug. See `src/data/generate_synthetic_data.py`'s `DRUG_CONFIGS` for the 10 protocols and `docs/05_api_contracts.md`'s updated auth section for how per-drug-owner access is enforced.

---

## 1. Protocol Specification

```json
{
  "protocol_id": "TRIAL-2026-ONC-04",
  "title": "Phase III Oncology Trial - Drug X",
  "visit_schedule": [
    {
      "visit_id": "V1",
      "name": "Baseline",
      "scheduled_day": 0,
      "window_days": 2,
      "required_procedures": ["vitals", "blood_draw", "informed_consent"]
    },
    {
      "visit_id": "V2",
      "name": "Week 4",
      "scheduled_day": 28,
      "window_days": 3,
      "required_procedures": ["vitals", "blood_draw", "dosing"]
    }
  ],
  "dosing_rules": {
    "drug": "Drug X",
    "min_mg": 50,
    "max_mg": 200,
    "route": "oral"
  },
  "banned_comedications": ["Warfarin", "St. John's Wort"],
  "ich_gcp_version": "E6(R2)"
}
```

## 2. Patient Visit Record

```json
{
  "visit_record_id": "REC-000123",
  "patient_id": "PT-04831",
  "site_id": "SITE-017",
  "protocol_id": "TRIAL-2026-ONC-04",
  "visit_id": "V2",
  "scheduled_date": "2026-08-15",
  "actual_date": "2026-08-21",
  "dosage_administered_mg": 220,
  "comedications": ["Warfarin"],
  "procedures_completed": ["vitals", "blood_draw"]
}
```

## 3. Deviation Record (output of Track A)

```json
{
  "deviation_id": "DEV-000456",
  "visit_record_id": "REC-000123",
  "patient_id": "PT-04831",
  "site_id": "SITE-017",
  "protocol_id": "TRIAL-2026-ONC-04",
  "type": "banned_comedication",
  "severity": "Major",
  "severity_rationale": "Warfarin is explicitly listed as a banned co-medication in Section 4.2; concurrent use poses a direct safety risk per ICH E6(R2) Section 4.5.",
  "protocol_clause_ref": "Section 4.2 - Prohibited Concomitant Medications",
  "detected_at": "2026-08-22T09:14:00Z",
  "detector_version": "rule-v1"
}
```

**Deviation `type` enum (extend as needed):** `missed_visit`, `late_visit`, `dosage_out_of_range`, `banned_comedication`, `missing_procedure`, `other`.

**`severity` enum (ICH E6 GCP):** `Major`, `Minor`, `Administrative`.

## 4. Site Risk Score (output of Track B)

```json
{
  "site_id": "SITE-017",
  "protocol_id": "TRIAL-2026-ONC-04",
  "risk_score": 78,
  "risk_band": "High",
  "computed_at": "2026-08-22T09:20:00Z",
  "indicator_breakdown": {
    "deviation_frequency": 0.32,
    "severity_mix_weight": 0.41,
    "recency_weight": 0.15,
    "trend_slope": 0.08,
    "repeat_offense_rate": 0.04
  },
  "trend": "worsening",
  "open_deviation_count": 14,
  "total_visits": 62
}
```

## 5. CAPA Report (output of Track C)

```json
{
  "capa_id": "CAPA-000789",
  "scope": "site",
  "site_id": "SITE-017",
  "related_deviation_ids": ["DEV-000456", "DEV-000461"],
  "root_cause": "Site staff are administering Drug X without cross-checking the concomitant medication list against Section 4.2 prior to dosing.",
  "corrective_action": "Retrain site coordinators on the prohibited medication list; implement a mandatory co-medication checklist before each dosing visit.",
  "preventive_action": "Add an automated co-medication check to the site's EDC entry workflow.",
  "suggested_owner_role": "Site Principal Investigator",
  "suggested_due_window_days": 14,
  "generated_at": "2026-08-22T09:25:00Z",
  "evidence_citations": ["DEV-000456", "Section 4.2 - Prohibited Concomitant Medications"],
  "protocol_id": "TRIAL-2026-ONC-04"
}
```

**Post-freeze addition:** `protocol_id` (new field, nothing renamed/removed) — derived from the report's underlying deviations, so a CAPA report on a site that hosts more than one protocol can still be attributed to the correct drug.

---

## 6. Synthetic Data Generation Guidance (Track C)

- Generate 15–20 sites, ~200–300 patients, ~2,000–5,000 visit records for a demo-scale dataset that still shows the "5,000+ visits / 200+ sites" scale claim proportionally (full scale is fine if performance allows).
- Deliberately seed a known set of deviations (e.g., 40–60) with pre-recorded expected type/severity, to use as the ground-truth test set for Track A's recall metric (see `01_project_planning.md` Section 8).
- Make 3–5 sites clearly high-risk (clustered severe deviations, worsening trend) and 3–5 clearly low-risk, so Track B's ranking is visibly sensible in the demo.
- Keep all identifiers synthetic (`PT-xxxxx`, `SITE-xxx`) — never use real names or real trial identifiers.
