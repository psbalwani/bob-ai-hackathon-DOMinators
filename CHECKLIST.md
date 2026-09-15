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

- [ ] Rule-based checks: visit window violations
- [ ] Rule-based checks: dosage-out-of-range
- [ ] Rule-based checks: banned co-medication present
- [ ] Rule-based checks: missing required procedure
- [ ] RAG layer over protocol text + ICH E6(R2) GCP guideline for ambiguous cases
- [ ] Severity classifier (Major / Minor / Administrative) with rationale + clause citation per deviation
- [ ] `POST /deviations/detect` endpoint live (FastAPI) — exposed early for Track D
- [ ] 10–15 seeded test cases (known planted deviations) validating recall
- [ ] Output matches `Deviation` object contract in `05_api_contracts.md`
- [ ] **Definition of done:** protocol + visit records → complete, correctly-classified, cited deviation list against seeded test cases

---

## Track B — Site-Level Risk Scoring (Owner: Data/AI #2) ⭐ my track

- [ ] Leading indicators + weighting defined and documented (frequency, severity mix, recency, trend, repeat-offense rate) — this is a judging talking point, write the rationale down
- [ ] Weighted scoring model implemented
- [ ] Trend calculation implemented (site improving/worsening over trial timeline)
- [ ] (Stretch) Secondary ML model calibrated against synthetic "site failed audit" labels
- [ ] `POST /risk-score/site` endpoint live
- [ ] `GET /risk-score/site/{site_id}` endpoint live
- [ ] Test case: clearly high-risk site
- [ ] Test case: clearly low-risk site
- [ ] Test case: edge case (few visits, one Major deviation) — confirms score isn't gameable by volume alone
- [ ] Output matches `RiskScore` object contract in `05_api_contracts.md`
- [ ] Built/tested against Track A's real output (not just mocked deviations)

---

## Track C — Data Engineering + CAPA Report Generation (Owner: Data/AI #3)

- [x] Synthetic data generator built (`src/data/generate_synthetic_data.py`) — first priority, unblocks A/B/D
- [ ] First dataset version (v1) generated and shipped to the team
- [ ] Full-scale dataset generated (5,000+ visits / 200+ sites) for final integration test
- [ ] ICH E6(R2) GCP guideline text curated/chunked for the vector store
- [ ] CAPA generator: retrieves relevant clause + deviation + site risk context (RAG)
- [ ] CAPA generator drafts Root Cause / Corrective Action / Preventive Action / suggested owner & due date
- [ ] `POST /capa/generate` endpoint live — exposed early for Track D
- [ ] Test cases confirming generated CAPA cites real evidence and does not hallucinate a protocol clause
- [ ] Output matches `CapaReport` object contract in `05_api_contracts.md`

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

- [ ] **Hour 4:** Track C's v1 synthetic dataset shipped
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
