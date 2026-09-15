# Bob Agent — Minimal Task Plan (Claude Code as Primary Build Tool)

**Strategy:** Claude Code builds the solution — all four tracks, most of the codebase. The Bob agent's 50 coins are spent on a **small number of one-shot, unmistakably repo-aware tasks**, run *after* the real code already exists. This keeps coin usage minimal while still satisfying the hackathon's "meaningful use of Bob" requirement — the two tasks below can only be done well by something that reads and reasons across multiple existing files, which is the actual point of Bob, not decorative usage.

> Still worth a 1–2 coin calibration test first (see the note in the previous version of this doc) so you know how far a coin goes before committing the two tasks below.

---

## The 2 tasks to definitely use Bob for

### Task 1 — Orchestration Pipeline Assembly
- **When:** after Claude Code has built Tracks A/B/C's individual modules and their endpoints exist in the repo.
- **Prompt shape (send everything in one message):** paste each module's actual function/endpoint signature (pull from `05_api_contracts.md` plus the real code), and ask Bob, in one shot, to write `run_pipeline(protocol_id)` in `orchestrator.py` that calls detect → score → generate CAPA → persist, matching the given signatures exactly.
- **Why this one:** it requires reading and reasoning across multiple already-existing files — the specific thing Bob is for, and not something a plain snippet generator does.

### Task 2 — Cross-file Contract Consistency Pass
- **When:** near the final integration checkpoint, once the whole repo is assembled.
- **Prompt shape:** paste `05_api_contracts.md` in full, and ask Bob to scan the actual implemented FastAPI routes in the repo and flag/fix any mismatches (field names, missing fields, wrong response shape) against the documented contract.
- **Why this one:** "an AI that understands your codebase" checking real, multi-file code against a spec is exactly the pitch — and it produces a clean, demonstrable session transcript for judges.

## Optional 3rd task — only if coins clearly remain

### Task 3 — Integration Test Generation for the Orchestrator
- One shot: "Generate pytest integration tests for `run_pipeline()` using the seeded synthetic dataset in `data/synthetic/`."
- Skip this by default. Tasks 1 and 2 alone are enough to demonstrate real, non-trivial Bob usage — don't spend coins here unless the calibration test shows you have plenty of headroom.

---

## Keeping each Bob task to one shot (protect the 50 coins)

- Paste **all** context up front — file paths, function signatures, the relevant schema/contract excerpt — in the first message. Don't let Bob explore the repo turn by turn if you can hand it the context directly.
- Run each task once Claude Code's output is already stable. Asking Bob to build against a moving target multiplies turns and burns coins.
- If the first response isn't quite right, give one precise correction ("keep everything, just rename `X` to `Y`") rather than restarting the conversation.

## Session history for submission

- Keep these as 2–3 separate, clearly named transcripts: `bob-session-01-pipeline-orchestration.md`, `bob-session-02-contract-consistency.md`, and optionally `bob-session-03-integration-tests.md`. Save them to `docs/bob-sessions/`.
- Add a short "Tooling" note in the README: Claude Code was the primary development assistant across the build; IBM Bob was used specifically for its repository-context-aware capabilities on integration and consistency checking — link each session. Being upfront about using both tools is fine — what the requirement cares about is that Bob's usage shown is real and non-trivial, not that Bob did all the work.
