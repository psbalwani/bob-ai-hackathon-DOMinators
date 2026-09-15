# CAPA Generator (Track C)

Generates a CAPA (Corrective and Preventive Action) report from one or more
`Deviation` objects, grounded in the protocol's own clause text and Track
C's curated ICH E6(R2) corpus (`src/data/ich_e6r2/`). See `DESIGN.md` for the
rationale behind the citation/hallucination guarantees, the fallback policy,
and the owner/due-window rules.

## Run standalone

```bash
python -m uvicorn src.capa.api:app --reload --port 8003
```

Loads `data/synthetic/` and runs Track A's real detector
(`src/detection/detector.py`) once at startup, so `POST /capa/generate`
works against real, live-detected deviations — no mocking needed.

## Endpoints (`docs/05_api_contracts.md`)

- `POST /capa/generate` — `{"scope": "deviation", "deviation_ids": ["DEV-000123"]}` or `{"scope": "site", "site_id": "SITE-017"}` (optionally with `deviation_ids` to restrict to specific ones at that site).
- `GET /capa/{capa_id}`
- `GET /capa/{capa_id}/export?format=pdf|markdown` — markdown always works; PDF requires the optional `fpdf2` dependency (`pip install fpdf2`), and returns `501 NOT_IMPLEMENTED` with a clear message if it isn't installed.

## Module layout

| File | Responsibility |
|---|---|
| `models.py` | `CapaReport` dataclass, matches `04_data_schema.md` section 5 field-for-field |
| `corpus.py` | Loads `src/data/ich_e6r2/guideline_chunks.json`; maps `(deviation type, severity)` to real, corpus-verified ICH chunks |
| `templates.py` | Deterministic root cause / corrective / preventive action text per deviation type, plus the owner-role/due-window severity policy |
| `llm_hook.py` | Optional watsonx.ai refinement of the narrative text only — never touches citations. Same resilience contract as `src/detection/llm_hook.py`: any failure returns `None` |
| `generator.py` | Orchestrates the above into one `CapaReport`, including site-level multi-type clustering |
| `store.py` | In-memory report store + `capa_id` counter + JSON snapshot, mirrors `src/detection/store.py` |
| `export.py` | Markdown (always) and PDF (optional `fpdf2`) rendering |
| `api.py` | The FastAPI service itself |

## Testing

```bash
pytest tests/test_capa.py -v
```

Covers: contract field-for-field conformance, deviation-scope and
site-scope (including multi-type clusters) generation, the deterministic
fallback path (no watsonx.ai credentials needed), and — the checklist's
explicit requirement — that every `evidence_citations` entry traces back to
a real deviation, a real protocol clause, or a real ICH corpus chunk.
