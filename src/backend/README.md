# Track D — Gateway & Orchestration

Wires Tracks A/B/C behind one API for the React dashboard (`src/frontend`), per
`docs/03_team_division.md` and `docs/05_api_contracts.md`'s "Orchestration / Dashboard
Aggregation" section.

## Run

```bash
uvicorn src.backend.app.main:app --reload --port 8000
```

## Design

- **In-process, not a proxy.** `app/pipeline.py` calls Track A/B/C's functions
  (`detect_deviations`, `compute_site_risk_score`/`rank_sites`, `capa.generator.generate`)
  directly in the same process, rather than making HTTP calls to their standalone
  services. This keeps `POST /pipeline/run` fast and dependency-free at demo time. Each
  track's own standalone service (ports 8001-8003) still exists separately and is
  unaffected — useful for isolated testing per `docs/03_team_division.md`.
- **Real Postgres with a graceful fallback.** `app/db.py` uses `DATABASE_URL` (e.g. a
  [Neon](https://neon.tech) connection string) if set, via SQLAlchemy
  (`app/models_db.py`: `deviations`, `site_risk_scores`, `capa_reports`,
  `pipeline_runs` — mirroring `docs/04_data_schema.md` sections 3-5). If unset, `app/persistence.py`
  transparently falls back to an in-memory store, so the app runs with zero DB setup —
  this doubles as the "cache a fallback for the live demo" requirement in
  `docs/03_team_division.md`'s Track D task list.
- **Dashboard aggregation endpoints** (`/sites`, `/sites/{id}`, `/sites/{id}/deviations`,
  `/sites/{id}/visits`, `/sites/{id}/capa`, `/deviations/{id}`) exist specifically to
  serve the four dashboard screens; they aren't part of the formal cross-track contract
  but are scoped to this track ("Dashboard Aggregation").
- Track A/B/C's own contract paths (`POST /deviations/detect`, `POST /risk-score/site`,
  `POST /capa/generate`, etc.) are also re-exposed here so the frontend only needs one
  base URL.

## Module layout

| File | Responsibility |
|---|---|
| `app/main.py` | FastAPI app, CORS, all routes |
| `app/pipeline.py` | `run_pipeline` (ingest → detect → score → CAPA → persist) and `dashboard_summary` |
| `app/db.py` | SQLAlchemy engine/session setup; `USING_DB` flag |
| `app/models_db.py` | SQLAlchemy tables for the three computed-result objects |
| `app/persistence.py` | Unified read/write interface — Postgres if configured, in-memory otherwise |
