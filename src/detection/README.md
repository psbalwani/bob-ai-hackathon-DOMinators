# Deviation Detection & Severity Classification (Track A)

Given a protocol spec + patient visit records (from
[`data/synthetic/`](../../data/synthetic/), produced by Track C), detects
protocol deviations and classifies each as `Major`/`Minor`/`Administrative`
per ICH E6(R2), with a one-line rationale and a real protocol clause
citation. Matches the `Deviation` object in
[`docs/04_data_schema.md`](../../docs/04_data_schema.md) section 3.

## Install & run

```bash
pip install -r requirements.txt
python -m uvicorn src.detection.api:app --reload --port 8001
```

On startup, if `data/synthetic/protocol.json` exists, the app auto-runs
detection once so `GET /deviations/site/{site_id}` works immediately without
a prior `POST`. Every detection run also snapshots its output to
`data/detected/deviations.json` (git-ignored, like `data/synthetic/`).

## Endpoints (see `docs/05_api_contracts.md`)

- `POST /deviations/detect` — `{"protocol_id": "...", "visit_record_ids": [...]}` (the second field is optional; omit it to run against every visit for the protocol). Returns `{"deviations": [...]}`.
- `GET /deviations/site/{site_id}` — returns `{"deviations": [...]}` for that site; `404` if the site isn't in the loaded dataset.

## How detection works

- `rules.py` — one pure, deterministic function per deviation type (`missed_visit`, `late_visit`, `dosage_out_of_range`, `banned_comedication`, `missing_procedure`). Only reads the protocol spec + a visit record; never the seeded ground truth.
- `severity.py` — classifies each finding into Major/Minor/Administrative. Every type is fully deterministic **except** the degree of lateness on a `late_visit` in the 2–3 extra-day boundary band, which is a genuine judgment call (mirrors the intentional overlap in the synthetic generator's own Minor-vs-Administrative lateness ranges).
- `retrieval.py` — the RAG layer's retrieval half: a local TF-IDF + cosine-similarity index (pure Python, no new dependency) over Track C's 11-chunk ICH E6(R2) corpus (`src/data/ich_e6r2/guideline_chunks.json`). Only invoked for the one ambiguous late-visit case, to fetch the guideline chunks that actually discuss it (`ICH-TAXONOMY-MINOR`/`ICH-TAXONOMY-ADMINISTRATIVE`) — chosen over a real vector DB (Chroma/FAISS) since the corpus is ~15 short documents and this keeps retrieval quality independent of network/credentials, unlike the LLM call it feeds into.
- `llm_hook.py` — the one hook to watsonx.ai, used only for that ambiguous boundary, given both the protocol clause and the chunks `retrieval.py` found. If `WATSONX_API_KEY` isn't set (or the call fails for any reason), it returns `None` and `severity.py` falls back to a fixed conservative default (`Minor`). The whole test suite is designed to pass on this fallback path with zero external calls; `retrieval.py`'s output still gets recorded in `severity_rationale` either way, since retrieval itself is local and always available.
- `detector.py` — orchestrates the above across a set of visit records into `Deviation` objects.
- `store.py` — in-memory store keyed by `site_id`, plus the JSON snapshot.

## Tests

```bash
pytest tests/test_rules.py tests/test_retrieval.py tests/test_detector_recall.py tests/test_api.py -v
```

`test_detector_recall.py` runs the real detector over the full synthetic
dataset and asserts recall ≥95% and severity agreement ≥85% against
`data/synthetic/seeded_deviations_ground_truth.json`, plus zero false
positives on clean records — matching the targets in
`docs/01_project_planning.md` section 8. It's skipped automatically if
`data/synthetic/` hasn't been generated yet.
