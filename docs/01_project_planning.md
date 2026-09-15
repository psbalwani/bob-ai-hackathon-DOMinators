# Project Planning — Clinical Trial Risk Monitor & Protocol Deviation Detector

**Hackathon:** IBM Bob Hackathon 2026
**Sector:** Pharma & Biotech
**Problem Statement:** P1 — Clinical Trial Risk Monitor & Protocol Deviation Detector (Critical Now)
**Team Size:** 4 (3 Data/AI, 1 Software Developer)

> **Assumption made:** the exact hackathon duration wasn't specified, so this plan is written for a standard **48-hour** hackathon format. If your event is shorter/longer, scale the timeline in Section 6 proportionally — the phase order and dependencies stay the same.

---

## 1. Problem Recap

A single clinical trial can involve **5,000+ patient visits across 200+ sites**. Protocol deviations — missed visits, incorrect dosing, banned co-medications — currently go undetected until an FDA audit. One rejected submission can delay drug approval by 6–12 months and cost $50–100M. Risk managers need **real-time visibility** into which sites are highest-risk *before* problems escalate.

### Challenge requirements (from the problem statement)
Build a Bob solution that:
1. Compares patient records against the protocol specification.
2. Classifies each deviation by severity per **ICH E6 GCP** (major / minor / administrative).
3. Scores site-level risk using leading indicators.
4. Generates **CAPA-ready** reports (Corrective and Preventive Action) with recommended mitigations.

---

## 2. Vision / One-Line Pitch

> "An AI copilot that continuously reads every patient visit against the trial protocol, flags and grades deviations the moment they happen, ranks sites by real risk — not gut feel — and drafts the CAPA report before the auditor even asks for one."

---

## 3. Goals & Objectives

| # | Objective | Maps to Challenge Requirement |
|---|-----------|-------------------------------|
| G1 | Automatically detect deviations by diffing patient visit records against structured protocol rules | 1 |
| G2 | Classify every detected deviation into Major / Minor / Administrative per ICH E6 GCP definitions, with a rationale | 2 |
| G3 | Produce a continuously updated, explainable **site risk score** from leading indicators (deviation frequency, severity mix, recency, trend) | 3 |
| G4 | Auto-generate a CAPA report per deviation/site cluster with root cause, corrective action, preventive action, and an owner/due-date scaffold | 4 |
| G5 | Present all of the above in a single risk-manager-facing dashboard with drill-down from trial → site → patient → visit | Supporting UX |

---

## 4. Scope

### In scope (hackathon MVP)
- Synthetic dataset generation (protocol spec + patient visit records) — see `04_data_schema.md`.
- Deviation detection engine (rules + LLM-assisted judgment for ambiguous cases).
- ICH E6 GCP severity classifier.
- Site-level risk scoring model (transparent, weighted-indicator based — not a black box, since risk managers must trust it).
- CAPA report generator (LLM-based, grounded in the specific deviation + protocol section).
- Web dashboard: trial overview, site risk ranking, deviation detail, CAPA export.
- Demo video + pitch deck.

### Out of scope (explicitly, for time-boxing)
- Integration with real EDC/CTMS systems (Medidata Rave, Veeva, etc.) — mocked instead.
- Multi-trial / multi-tenant support.
- Full 21 CFR Part 11 e-signature compliance workflow (acknowledge it in the design, don't build it).
- Mobile app.

---

## 5. User Personas

| Persona | Need |
|---|---|
| **Clinical Risk Manager** | Wants a ranked list of at-risk sites and *why*, updated continuously, not a static quarterly report. |
| **Clinical Research Associate (CRA)** | Needs to know exactly which visits/patients at their assigned sites have open deviations. |
| **Regulatory/QA Lead** | Needs CAPA documentation that is audit-ready and traceable to the protocol clause it violates. |
| **Site Coordinator** | Wants early warning before a minor issue becomes a major finding. |

---

## 6. Functional Requirements

| ID | Requirement | Priority |
|---|---|---|
| FR1 | System ingests a structured protocol specification (visit schedule, dosing rules, allowed/banned co-medications, required procedures) | Must |
| FR2 | System ingests patient visit records (actual vs. scheduled) | Must |
| FR3 | System detects deviations: missed/late visits, dosing out of range, banned co-medication present, missing procedure | Must |
| FR4 | Each deviation is classified Major/Minor/Administrative with a written rationale citing the protocol clause | Must |
| FR5 | Each site gets a numeric risk score (0–100) with a breakdown of contributing indicators | Must |
| FR6 | Risk scores are ranked and trended over time (is this site getting better or worse?) | Should |
| FR7 | CAPA report auto-drafted per deviation or per site risk cluster, exportable as PDF/Markdown | Must |
| FR8 | Dashboard: trial-level summary → site drill-down → patient/visit drill-down | Must |
| FR9 | Every AI-generated classification/score/report is explainable (shows the evidence it used) | Must |
| FR10 | Audit log of what was flagged, when, and by which rule/model version | Should |

## 7. Non-Functional Requirements

- **Explainability:** every AI output (severity label, risk score, CAPA text) must show its evidence — this is a compliance domain, "black box" outputs will not be trusted by judges or real users.
- **Auditability:** all detections/classifications are logged and traceable.
- **Data privacy:** use only synthetic data; design as if handling PHI (role-based access, no PII in logs) even though the hackathon data isn't real.
- **Performance:** should handle the reference scale (5,000+ visits / 200+ sites) in the demo dataset without noticeable lag in the dashboard.
- **Regulatory alignment:** severity taxonomy must map explicitly to ICH E6(R2) GCP definitions.

---

## 8. Success Metrics (for the demo / judging)

| Metric | Target |
|---|---|
| Deviation detection recall on seeded test cases | ≥ 95% of injected deviations caught |
| Severity classification agreement with a rubric/ground truth | ≥ 85% |
| Time to generate a CAPA report (vs. manual, cited as weeks) | < 30 seconds in demo |
| Risk score explainability | Every score has a visible, human-readable breakdown |
| End-to-end demo runs live without manual data massaging | Yes/No |

---

## 9. Assumptions & Constraints

- No real patient data is available or should be used — a synthetic, but realistic, dataset will be generated (see `04_data_schema.md`).
- ICH E6(R2) GCP severity definitions will be used as the classification rubric (major/minor/administrative), since the problem statement names this standard explicitly.
- The team will use IBM watsonx.ai (or equivalent available foundation model access) for the LLM-assisted components, and **IBM Bob** as the AI pair-programming/dev-acceleration tool while building — per the hackathon's requirement that submissions demonstrably use Bob.
- Team has 3 Data/AI + 1 Developer — architecture and task division are designed around this ratio (see `03_team_division.md`).

---

## 10. Timeline (48-hour reference — rescale as needed)

| Phase | Time Window | Focus |
|---|---|---|
| 0. Kickoff | Hour 0–2 | Confirm scope, finalize data schema & API contracts, assign tracks |
| 1. Build (parallel) | Hour 2–20 | Each track builds its module independently against the shared contract |
| 2. First Integration Checkpoint | Hour 20–24 | Wire modules together end-to-end with stub/synthetic data; fix interface mismatches |
| 3. Build (parallel, round 2) | Hour 24–36 | Deepen models, polish UI, add explainability, harden edge cases |
| 4. Final Integration | Hour 36–42 | Full pipeline test, bug bash, performance pass |
| 5. Polish & Demo Prep | Hour 42–46 | Pitch deck, demo script, rehearsal (see `06_demo_pitch_script.md`) |
| 6. Submission Buffer | Hour 46–48 | Buffer for submission platform issues, final commit, README |

---

## 11. Deliverables Checklist

- [ ] GitHub repo (this document set lives in `/docs`)
- [ ] Working end-to-end demo (deviation detection → risk score → CAPA report → dashboard)
- [ ] Synthetic dataset + generator script
- [ ] Architecture document (`02_architecture.md`)
- [ ] Team division / task board (`03_team_division.md`)
- [ ] Data schema (`04_data_schema.md`) and API contracts (`05_api_contracts.md`)
- [ ] 3–5 min demo video
- [ ] Pitch deck (5–7 slides)
- [ ] README with setup instructions

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Modules don't integrate cleanly at the end | High | Freeze data schema & API contracts on Hour 0–2; integrate early (Hour 20), not just at the end |
| LLM outputs are inconsistent/hallucinate protocol clauses | High | Ground generation in retrieved protocol text (RAG), not free generation; show citations |
| One Data/AI track runs long and blocks integration | Medium | Each track ships a stubbed/mocked interface by Hour 4 so others aren't blocked |
| Dev is a bottleneck for both backend and frontend | Medium | Data/AI folks each expose their module via a simple FastAPI endpoint themselves; Dev focuses on orchestration, dashboard, and deployment |
| Synthetic data doesn't look "realistic" to judges | Medium | Base ranges/co-medication lists/visit windows on the referenced standards (ICH E6, real trial visit-window conventions) |

---

## 13. Tools & Resources

- **AI/Dev partner:** IBM Bob (required — demonstrate meaningful use per hackathon rules)
- **Foundation models:** IBM watsonx.ai (or team's available LLM access) for classification rationale + CAPA generation
- **Backend:** Python (FastAPI)
- **Frontend:** React
- **Storage:** PostgreSQL (structured) + a lightweight vector store for protocol/ICH guideline retrieval
- **Collaboration:** GitHub (branch-per-track), shared task board (Trello/Linear/GitHub Projects), Slack/Discord for standups
