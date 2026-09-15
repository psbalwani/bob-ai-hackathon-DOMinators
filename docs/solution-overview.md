# Solution Overview

## What We Built

An AI copilot that continuously reads every patient visit against the trial protocol, flags and grades deviations the moment they happen, ranks sites by real risk — not gut feel — and drafts the CAPA (Corrective and Preventive Action) report before an auditor ever asks for one.

## How It Works

1. A structured **protocol specification** (visit schedule, dosing rules, banned co-medications, required procedures) and **patient visit records** (actual vs. scheduled) are ingested and validated.
2. The **Deviation Detection Engine** compares each visit against the protocol: deterministic rule checks catch missed/late visits, dosing out of range, banned co-medications, and missing procedures; an LLM-assisted judgment layer (grounded via RAG over the protocol text and ICH E6(R2) GCP guideline) handles ambiguous cases and returns a cited determination.
3. Every detected deviation is classified **Major / Minor / Administrative** per ICH E6(R2) GCP, with a written rationale citing the specific protocol clause.
4. The **Site Risk Scoring Engine** rolls deviations up per site into a transparent, weighted 0–100 risk score (deviation frequency, severity mix, recency, trend, repeat-offense rate) — with the indicator breakdown always visible, not a black-box number.
5. The **CAPA Report Generator** drafts a Root Cause, Corrective Action, Preventive Action, and a suggested owner/due-date for each deviation or site cluster, grounded in the same protocol clause and citing its evidence.
6. A **dashboard** presents all of this with drill-down from trial → site → patient → visit, so a risk manager can go from "which site is worst" to "which exact clause was violated and why" in a few clicks.

## Architecture Diagram

> See [`architecture.md`](architecture.md) for the detailed diagram.

```
[Protocol Spec + Visit Records] → [Deviation Detection] → [Site Risk Scoring] → [CAPA Generator]
                                                                  ↓
                                                        [FastAPI] → [React Dashboard]
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Transparent, weighted-indicator risk score instead of an opaque ML model | Risk managers in a regulated domain must be able to trust and audit the score, not just see a number |
| Ground severity rationale and CAPA generation in retrieved protocol/ICH text (RAG), not free-form LLM generation | Prevents hallucinated protocol clauses — every claim is traceable to a real source |
| Rule layer first, LLM judgment only for ambiguous cases | Deterministic checks (visit window, dosage range, banned co-med list) are cheap, fast, and don't need a model; the LLM is reserved for genuinely ambiguous determinations |
| Every AI output carries its evidence (clause citation, indicator breakdown, source deviation IDs) | Explainability is a hard requirement, not a nice-to-have — this is the difference between a tool QA/Regulatory will trust and one they'll reject as a "black box" |
| Freeze the data schema and API contracts in the first hours of the build | Let four workstreams (deviation detection, risk scoring, CAPA generation, platform/dashboard) build in parallel against one shared contract |

## IBM Technologies Used

- **IBM watsonx.ai (or team's available foundation model access):** used for the LLM-assisted deviation judgment (ambiguous co-medication/procedure cases), the ICH E6(R2) GCP severity classification rationale, and CAPA report generation — each grounded via RAG over the protocol text and guideline knowledge base rather than free generation.
- **IBM Bob:** used as the AI dev-acceleration partner during the build — specifically for repo-aware tasks that require reasoning across multiple existing files, such as assembling the end-to-end orchestration pipeline (`detect → score → generate CAPA → persist`) from the already-built module signatures, and a cross-file consistency pass checking the implemented FastAPI routes against the documented API contract. See `docs/bob-sessions/` for session transcripts once available.
