# ClinIQ — Master Submission Checklist (A–Z)

**Team:** DOMinators · **Track:** AI · **Submission window:** 15 Sep 2026, 12:00 PM – 11:45 PM

This is the single source of truth for what's left before submission. It covers all 4 build tracks (`docs/03_team_division.md`) plus every hard requirement from the IBM Bob User Guide and the Bobathon Submission Template Guide.

---

## 🚨 MANDATORY RULE FOR ALL AI AGENTS (Bob / Claude / any assistant working in this repo)

> **Any AI agent that completes a task tracked in this file MUST tick the corresponding `- [ ]` box (`- [x]`) in the same commit/session that finishes the work — before reporting the task as done to the user.**
>
> - Do not mark a box done unless the work is actually verifiable (code exists, file has real content, test passes, endpoint responds).
> - If a box is partially done, leave it unchecked and add a one-line sub-note under it rather than checking it prematurely.
> - If you add new work not covered here, add a new checklist line instead of silently doing untracked work.
> - Never delete or renumber existing checklist items — only check them off or annotate them.
> - This file is process state, not documentation — keep edits to checkbox status and short notes only.

---

## 0. Hour 0–2: Freeze the Contracts (blocks everyone)

- [ ] `docs/04_data_schema.md` reviewed and frozen by all 4 tracks
- [ ] `docs/05_api_contracts.md` reviewed and frozen by all 4 tracks
- [ ] Mock shapes for `Deviation`, `RiskScore`, `CapaReport` agreed so B/C can build before A ships

---

## Track A — Deviation Detection & Severity Classification (Owner: Data/AI #1)

- [x] Rule-based checks: visit window violations (`src/detection/rules.py::check_late_visit`, `check_missed_visit`)
- [x] Rule-based checks: dosage-out-of-range (`check_dosage_out_of_range`)
- [x] Rule-based checks: banned co-medication present (`check_banned_comedication`)
- [x] Rule-based checks: missing required procedure (`check_missing_procedure`)
- [x] RAG layer over protocol text + ICH E6(R2) GCP guideline for ambiguous cases — `src/detection/retrieval.py`: a local TF-IDF + cosine-similarity index (pure Python, no new dependency) over Track C's 11-chunk ICH E6(R2) corpus. For the one ambiguous case (late-visit severity boundary), it retrieves the relevant guideline chunks and both the protocol clause text and the retrieved chunks are passed to the live watsonx.ai chat call (`llm_hook.py`); the retrieved citations are also recorded in `severity_rationale`, satisfying FR9 (explainability). Verified: the retrieval query used in production retrieves exactly `ICH-TAXONOMY-MINOR`/`ICH-TAXONOMY-ADMINISTRATIVE` (`tests/test_retrieval.py`), and a live run against the full synthetic dataset shows real deviations citing that retrieved grounding in their rationale
- [x] Severity classifier (Major / Minor / Administrative) with rationale + clause citation per deviation (`src/detection/severity.py`)
- [x] `POST /deviations/detect` endpoint live (FastAPI) — exposed early for Track D (`src/detection/api.py`; run with `python -m uvicorn src.detection.api:app --reload --port 8001`); also `GET /deviations/site/{site_id}` per contract
- [x] 10–15 seeded test cases (known planted deviations) validating recall — exceeded: scored against all 52 real seeded deviations in `data/synthetic/seeded_deviations_ground_truth.json` (`tests/test_detector_recall.py`), plus 17 constructed unit tests (`tests/test_rules.py`)
- [x] Output matches `Deviation` object contract in `05_api_contracts.md` — field-for-field verified (`tests/test_api.py`), including the shared error convention
- [x] **Definition of done:** protocol + visit records → complete, correctly-classified, cited deviation list against seeded test cases — 100% recall (52/52), 0 false positives, 96.2% severity agreement against ground truth, all verified live including the watsonx.ai path

---

## Track B — Site-Level Risk Scoring (Owner: Data/AI #2) ⭐ my track

- [x] Leading indicators + weighting defined and documented (frequency, severity mix, recency, trend, repeat-offense rate) — this is a judging talking point, write the rationale down (`src/risk_scoring/DESIGN.md`)
- [x] Weighted scoring model implemented (`src/risk_scoring/indicators.py`, `scoring.py`) — sanity-checked against the real synthetic dataset: top 5 by `risk_score` are exactly the 5 seeded high-tier sites, zero-deviation sites score 0
- [x] Trend calculation implemented (site improving/worsening over trial timeline) — `src/risk_scoring/trend.py`, tercile comparison with calibrated noise threshold; verified 12/17 sites match `seed_trend_intent` (volatile detection is the known weak point at this sample size, documented in the module)
- [ ] (Stretch) Secondary ML model calibrated against synthetic "site failed audit" labels — no such ground-truth label actually exists in the generated dataset (only `seed_risk_tier`/`seed_trend_intent`, the same metadata that seeds the deviations); training against a label derived from that would be circular, not real calibration. Recommend skipping and recording as a known limitation rather than building a hollow model, pending final call.
- [x] `POST /risk-score/site` endpoint live (`src/risk_scoring/api.py`, standalone FastAPI service on port 8002; run with `uvicorn src.risk_scoring.api:app --reload --port 8002`) — manually verified against real dataset (200 + error cases)
- [x] `GET /risk-score/site/{site_id}` endpoint live (same service) — also `GET /risk-score/ranking?protocol_id=...` per contract
- [x] Test case: clearly high-risk site (`tests/test_risk_scoring.py::test_clearly_high_risk_site` — every indicator saturated, `risk_score == 100`)
- [x] Test case: clearly low-risk site (`test_clearly_low_risk_site`, plus `test_zero_deviations_is_low_not_gamed_the_other_way`)
- [x] Test case: edge case (few visits, one Major deviation) — confirms score is rate-driven, not raw-count-driven (`test_one_major_deviation_scores_by_rate_not_raw_count`: identical single deviation scores 70/High at 2 visits vs 9/Low at 200 visits). All 4 tests pass.
- [x] Output matches `RiskScore` object contract in `05_api_contracts.md` (field-for-field, including the error convention `{"error": {"code", "message"}}` — verified 404/400 cases manually)
- [x] Built/tested against Track A's real output (not just mocked deviations) — `loaders.py` now prefers Track A's real detector snapshot (`data/detected/deviations.json`, `detector_version: "rule-v1"`) over the mock when present, falling back gracefully otherwise. Verified: demo-scale ranking still puts all 5 seeded high-tier sites on top; full-scale (220 sites) reproduces Track C's documented 59/61 (96.7%) benchmark exactly. Fixed a real port collision found along the way: Track A's and Track B's standalone services were both hardcoded to 8001 — Track B moved to 8002.

---

## Track C — Data Engineering + CAPA Report Generation (Owner: Data/AI #3)

- [x] Synthetic data generator built (`src/data/generate_synthetic_data.py`) — first priority, unblocks A/B/D
- [x] First dataset version (v1) generated and shipped to the team — `data/synthetic/` (18 sites, 289 patients, 2,023 visits, 52 seeded deviations, seed=42); Tracks A/B/C tests all run against it live
- [x] Full-scale dataset generated (5,000+ visits / 200+ sites) for final integration test — `--num-sites` flag added; validated at 220 sites / 3,730 patients / 26,110 visits / 658 deviations (~3s to generate); full A→B→C pipeline run against it: detection 0.35s, ranking 0.68s (59/61 top-risk sites = seed-tier-high, all seed-tier-low sites scored 0), CAPA gen <10ms per site -- see `src/data/README.md` "Full-scale dataset" section for the exact command and numbers
- [x] ICH E6(R2) GCP guideline text curated/chunked for the vector store (`src/data/ich_e6r2/guideline_chunks.json`, 11 chunks: 8 ICH-section paraphrases + 3 internal Major/Minor/Administrative taxonomy notes) -- content/chunking done; embedding into a live Chroma/FAISS index is still Track A's RAG layer to wire up
- [x] CAPA generator: retrieves relevant clause + deviation + site risk context (RAG) — `src/capa/corpus.py` (deterministic `(type, severity) -> chunk_id` retrieval over the ICH corpus, corpus-verified) + `src/capa/generator.py`; site risk score itself deliberately not folded into report content -- see `src/capa/DESIGN.md` "What's intentionally out of scope"
- [x] CAPA generator drafts Root Cause / Corrective Action / Preventive Action / suggested owner & due date — `src/capa/templates.py` (deterministic, always available) + `src/capa/llm_hook.py` (optional watsonx.ai refinement of prose only, same fail-safe contract as Track A's hook)
- [x] `POST /capa/generate` endpoint live — exposed early for Track D (`src/capa/api.py`; run with `python -m uvicorn src.capa.api:app --reload --port 8003`); also `GET /capa/{capa_id}` and `GET /capa/{capa_id}/export?format=pdf|markdown` per contract (markdown always works; PDF needs optional `fpdf2`)
- [x] Test cases confirming generated CAPA cites real evidence and does not hallucinate a protocol clause — `tests/test_capa.py::test_evidence_citations_never_hallucinate` (every citation checked against real deviation ids / real protocol clauses / real ICH corpus chunks) + 16 more covering contract shape, clustering, severity-driven owner/due-window, and the API; 17/17 pass
- [x] Output matches `CapaReport` object contract in `05_api_contracts.md` — field-for-field verified (`tests/test_capa.py::test_single_deviation_report_matches_contract_shape`)

---

## Track D — Backend Integration, Dashboard & Deployment (Owner: Developer)

- [ ] FastAPI gateway stood up
- [ ] PostgreSQL schema stood up per `04_data_schema.md`
- [ ] Initial proxy to each track's stub endpoints working
- [ ] Orchestration flow built: ingest → detect → score → generate CAPA → persist
- [ ] React dashboard — Trial Overview (ranked sites)
- [ ] React dashboard — Site Drill-down (indicator breakdown, deviation list, trend)
- [ ] React dashboard — Patient/Visit Drill-down (deviation detail + citation)
- [ ] React dashboard — CAPA export view
- [ ] Graceful failure handling (cached pre-generated results as live-demo fallback)
- [ ] Docker Compose for one-command local demo
- [ ] Bob usage log kept with concrete examples (needed for submission — "meaningful use of Bob" is judged)

---

## Integration Checkpoints

- [x] **Hour 4:** Track C's v1 synthetic dataset shipped — `data/synthetic/` (see Track C section above)
- [ ] **Hour 20–24 (First Integration):** every track's endpoint live (even rough); Track D wires full pipeline end-to-end; interface mismatches fixed immediately
- [ ] **Hour 24–36:** hardening pass — deepen models, add explainability detail, polish UI, expand tests
- [ ] **Hour 36–42 (Final Integration):** full pipeline test at 5,000+ visits / 200+ sites scale, bug bash, performance pass
- [ ] **Hour 42–46:** demo prep per `docs/06_demo_pitch_script.md`

---

## Template-Required Files (Bobathon Submission Template Guide)

### `submission.yaml` — read by evaluators first
- [x] `team.name`, `team.track`, `team.lead`, `team.members` filled
- [x] `submission.title`, `problem_statement`, `solution_summary` filled
- [x] `key_features` (3–5) filled
- [x] `tech_stack` (languages/frameworks/ibm_technologies/databases/other) filled
- [x] `what_we_are_most_proud_of` filled
- [x] `known_limitations` filled (honest gaps — don't overclaim)
- [ ] Re-check no field is blank once tracks A/B/D land real code (tech stack list may need updates)

### `README.md` — human-readable front page
- [ ] `[Your Project Title Here]` replaced
- [ ] Team table filled (name, track, lead, members)
- [ ] Problem Statement section written (2–3 sentences)
- [ ] Solution section written (2–3 sentences)
- [ ] Key Features (3–5) written, matching what's actually implemented
- [ ] Tech Stack table filled
- [ ] How to Run — exact commands copied from `docs/setup-guide.md`
- [ ] Demo links section filled (video / live demo / screenshots / presentation)
- [ ] Known Limitations section filled
- [ ] What We're Most Proud Of section filled
- [ ] **Final check:** search README for `[` — zero remaining placeholders

### `docs/`
- [ ] `docs/problem-statement.md` — written (audience, why existing solutions fail, quantified pain, why now)
- [ ] `docs/solution-overview.md` — written (core mechanism, differentiation, design decisions, UX)
- [ ] `docs/architecture.md` — diagram (Mermaid or image) + component table + end-to-end data flow + security/scalability notes
- [ ] `docs/setup-guide.md` — prerequisites, every env var, exact install/run commands, how to verify it works, troubleshooting table
- [ ] `docs/setup-guide.md` tested end-to-end by a teammate on a clean terminal

### `src/`
- [ ] All source code for Tracks A/B/C/D committed under `src/`
- [ ] `src/.env.example` updated with every env var the code actually needs (dummy values OK)
- [ ] `src/README.md` explains layout (esp. since this is a multi-track monorepo — frontend/backend/tracks)
- [ ] No `.env`, `node_modules/`, `__pycache__/`, `.venv/`, or build artefacts committed (`git status` check)

### `demo/`
- [ ] `demo/demo-video-link.txt` — real URL, not the placeholder (3–5 min, shows app running, real user journey, real output, "anyone with link" access)
- [ ] `demo/live-demo-url.txt` — real deployed URL, or `NOT DEPLOYED` (currently still placeholder text)
- [ ] `demo/screenshots/` — at least 3 screenshots, named sequentially (`01-...png`, `02-...png`, `03-...png`)

### `presentation/`
- [ ] `presentation/slides.pdf` (preferred) or `slides.pptx` added
- [ ] Deck covers, in order: Problem → Solution → Demo/architecture → IBM Bob integration → Impact

### Do-not-touch template rules
- [ ] `CONTRIBUTING.md` still present (not deleted)
- [ ] `.gitignore` untouched / still excludes `.env`, `node_modules`
- [ ] `.github/workflows/validate.yml` **not modified**
- [ ] Top-level directory structure unchanged (only contents inside `src/` are free-form)

---

## Automated Validation

- [ ] Latest push shows **Validate Submission** GitHub Action GREEN 🟢 (repo → Actions tab)
- [ ] If red: open the run, read the error, fix, push again (don't ignore it)

---

## Final Submission Checklist (do this last, in order)

- [ ] Repository is **Public**
- [ ] Official IBM Bobathon template structure intact (nothing renamed/deleted)
- [ ] `submission.yaml` — all `# REQUIRED` fields filled, matches actual implementation
- [ ] `README.md` — zero `[placeholder]` text remaining
- [ ] `docs/problem-statement.md`, `docs/solution-overview.md`, `docs/architecture.md`, `docs/setup-guide.md` all written (not template text)
- [ ] `src/` — all source code committed, `.env.example` current
- [ ] `demo/demo-video-link.txt` — real working video URL
- [ ] `demo/screenshots/` — ≥3 screenshots of the running app
- [ ] `presentation/slides.pdf` (or `.pptx`) present
- [ ] No `.env` files committed (`git log` check if unsure)
- [ ] No `node_modules/`, `.venv/`, build artefacts committed
- [ ] GitHub Actions **Validate Submission** is green
- [ ] Repository confirmed Public
- [ ] Entry form submitted at https://ibm.biz/bob-ai-charusat before **11:45 PM, 15 Sep 2026**
- [ ] Repo URL double-checked in the submission form

---

## Reminders (Common Mistakes — from the Submission Guide)

- [ ] README has no leftover `[` characters
- [ ] `.env` never committed with real credentials
- [ ] `demo-video-link.txt` does not still contain `your-demo-video-link-here`
- [ ] `live-demo-url.txt` does not still contain `your-live-demo-url-here`
- [ ] Repo visibility is Public, not Private
- [ ] `src/` is not empty / not only boilerplate — must contain real track code
- [ ] Video link uses "anyone with the link" permissions
