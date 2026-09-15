# Team Division — 4 Parallel Tracks

Team: **3 Data/AI + 1 Developer.** Split into four parallel, largely independent tracks that meet at defined integration checkpoints. Each track owns one column of the architecture in `02_architecture.md` and must respect the shared contracts in `04_data_schema.md` and `05_api_contracts.md` — **freeze those two docs in the first 2 hours** so no one is blocked later.

---

## Track A — Deviation Detection & Severity Classification
**Owner:** Data/AI #1

**Goal:** Given a protocol spec + patient visit record, output a list of classified deviations.

**Tasks:**
1. Build rule-based checks: visit window violations, dosage-out-of-range, banned co-medication present, missing required procedure.
2. Build the RAG layer over the protocol text + ICH E6(R2) GCP guideline for ambiguous cases.
3. Implement the severity classifier (Major/Minor/Administrative) with a one-line rationale + clause citation for each deviation.
4. Expose the module as its own small FastAPI endpoint early (`POST /deviations/detect`) so Track D can integrate against it without waiting.
5. Write 10–15 seeded test cases (known deviations planted in synthetic data) to validate recall.

**Output contract:** `Deviation` object — see `05_api_contracts.md`.

**Definition of done:** given a protocol + visit record set, returns a complete, correctly-classified, cited deviation list against the seeded test cases.

---

## Track B — Site-Level Risk Scoring
**Owner:** Data/AI #2

**Goal:** Given a site's deviations + visit volume, output a risk score with an explainable breakdown.

**Tasks:**
1. Define the leading indicators and weighting (deviation frequency, severity mix, recency, trend, repeat-offense rate) — document the rationale, this is a judging talking point.
2. Implement the weighted scoring model.
3. Implement trend calculation (is the site improving or worsening over the trial timeline).
4. (Stretch) Calibrate against a secondary ML model trained on synthetic "site failed audit" labels.
5. Expose as `POST /risk-score/site` and `GET /risk-score/site/{site_id}` early for Track D.
6. Write test cases: a clearly high-risk site, a clearly low-risk site, an edge case (few visits, one Major deviation) to sanity-check the score isn't gameable by volume alone.

**Output contract:** `RiskScore` object — see `05_api_contracts.md`.

**Depends on:** Track A's deviation output (can build against mocked deviations until Track A is ready — agree on the mock shape in hour 0–2).

---

## Track C — Data Engineering + CAPA Report Generation
**Owner:** Data/AI #3

**Goal:** (1) Produce the synthetic dataset everyone builds/tests against. (2) Generate CAPA-ready reports from deviations.

**Tasks:**
1. **First priority (hour 0–4, blocks everyone else):** build the synthetic data generator — protocol spec + realistic patient visit records with deliberately seeded deviations of known type/severity, per `04_data_schema.md`. Ship a first dataset version fast so Tracks A/B/D aren't idle.
2. Build/curate the ICH E6(R2) GCP guideline text for the vector store.
3. Build the CAPA generator: retrieves the relevant clause + deviation + site risk context (RAG), drafts Root Cause / Corrective Action / Preventive Action / suggested owner & due date.
4. Expose as `POST /capa/generate` early for Track D.
5. Write test cases checking the generated CAPA cites real evidence and doesn't hallucinate a protocol clause.

**Output contract:** `CapaReport` object — see `05_api_contracts.md`.

**Depends on:** Track A's deviation output for real (non-mock) generation; can mock initially.

---

## Track D — Backend Integration, Dashboard & Deployment
**Owner:** Developer

**Goal:** Wire Tracks A/B/C together behind one API and present it in a usable dashboard.

**Tasks:**
1. Hour 0–2: agree the API contracts and data schema with the other three (this doc's dependencies exist because of this step — don't skip it).
2. Stand up the FastAPI gateway + PostgreSQL schema per `04_data_schema.md` / `05_api_contracts.md`; initially proxy to each track's own stub endpoints.
3. Build the orchestration flow: ingest → detect → score → generate CAPA → persist.
4. Build the React dashboard: Trial Overview (ranked sites) → Site Drill-down (indicator breakdown, deviation list, trend) → Patient/Visit Drill-down (deviation detail + citation) → CAPA export view.
5. Handle failure gracefully (cache a few pre-generated results as a live-demo fallback).
6. Docker Compose for one-command local demo.
7. Use IBM Bob throughout and keep a short log of concrete usage examples (needed for the submission/demo — "meaningful use of Bob" is a judged requirement).

**Depends on:** all three other tracks for full integration, but can build the shell, DB schema, and UI against mocked data from hour 0.

---

## Integration Plan

- **Hour 0–2:** All four freeze `04_data_schema.md` and `05_api_contracts.md` together. This is the single most important meeting — do not skip it.
- **Hour 4:** Track C ships v1 synthetic dataset. Tracks A/B/D unblocked to build against real (if small) data.
- **Hour 20–24 (First Integration Checkpoint):** Each track's endpoint is live, even if rough. Track D wires the full pipeline end-to-end. Fix interface mismatches immediately — this is why the contract was frozen early.
- **Hour 24–36:** Parallel hardening — deepen models, add explainability detail, polish UI, expand test cases.
- **Hour 36–42 (Final Integration):** Full pipeline test with the complete synthetic dataset (5,000+ visits / 200+ sites scale), bug bash, performance pass.
- **Hour 42–46:** Demo prep — see `06_demo_pitch_script.md`.

## Git Workflow

- `main` branch protected; each track works on `track-a-deviation`, `track-b-risk`, `track-c-capa`, `track-d-platform`.
- PR into `main` at each integration checkpoint, one other teammate reviews before merge.
- Keep the shared `data_schema` and `api_contracts` docs as the source of truth — if a track needs to deviate from them, flag it in the team channel before changing the contract, not after.

## Communication Cadence

- Short standup every ~4–6 hours: what's done, what's blocked, any contract change needed.
- Shared task board (GitHub Projects/Trello/Linear) mirroring the tasks above, one card per task.
- Anyone blocked for more than 30 minutes flags it immediately rather than working around it silently — with only 4 people, one silent blocker can sink the timeline.
