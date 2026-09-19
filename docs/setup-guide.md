# Setup Guide

> **This file is read by the automated evaluation pipeline. Be precise and complete.**

## Prerequisites

- [ ] Python 3.11+
- [ ] Node.js 18+
- [ ] An IBM Cloud account with watsonx.ai access (optional — see below)
- [ ] A Neon (or any hosted) PostgreSQL connection string (optional — see below)

## Environment Variables

Copy `src/.env.example` to `src/.env` and fill in the values you want to use:

```bash
cp src/.env.example src/.env
```

| Variable | Description | Required |
|---|---|---|
| `WATSONX_API_KEY` | IBM watsonx.ai API key | No — only used for the one ambiguous late-visit severity case in Track A's detector (`src/detection/llm_hook.py`) and for optional CAPA narrative refinement (`src/capa/llm_hook.py`); without it, both fall back to deterministic behavior and everything else works unchanged |
| `WATSONX_URL` | watsonx.ai region endpoint, e.g. `https://eu-de.ml.cloud.ibm.com` | Only if using the above |
| `WATSONX_SPACE_ID` | watsonx.ai deployment space ID — **preferred** over `WATSONX_PROJECT_ID`; a project without an attached WML instance will 403 even with valid credentials | Only if using the above |
| `WATSONX_PROJECT_ID` | watsonx.ai project ID (fallback if no space is available) | Only if using the above |
| `WATSONX_MODEL_ID` | Model to call, e.g. `ibm/granite-13b-instruct-v2` | No (has a default) |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Fallback LLM option | No — skeleton only, not wired into any code path yet |
| `DATABASE_URL` | A PostgreSQL connection string (e.g. from [Neon](https://neon.tech), `postgresql://user:pass@host/db`) | No — Track D's backend (`src/backend`) falls back to an in-memory store if this isn't set, so the app runs with zero DB setup. Set this to get real persistence across restarts. |
| `APP_PORT` | Backend gateway port | No (default `8000`) |
| `TOKEN_SECRET` | Signing secret for drug-owner login tokens (`src/backend/app/auth.py`) | No — falls back to an insecure dev default so `uvicorn --reload` works out of the box locally; set a real random value for any non-local deployment |

The frontend (`src/frontend`) reads its own `.env` — copy `src/frontend/.env.example` to `src/frontend/.env.local` if the backend isn't on the default `http://localhost:8000`.

### Logging in (multi-drug dashboard)

The gateway now requires login — there are 11 seeded demo accounts, one per drug trial plus one portfolio account that owns all 10 (see `src/backend/app/auth.py`'s `ALL_PROTOCOL_IDS`/`_seed_users`). All seeded accounts share the same demo password.

| Username | Owns |
|---|---|
| `owner_onc04` .. `owner_onc13` | One drug each (`TRIAL-2026-ONC-04` .. `TRIAL-2026-ONC-13`) |
| `owner_portfolio` | All 10 drugs — shows a drug switcher in the sidebar |

Password for every seeded account: `changeme123`. **Demo-only** — never reuse this for a real deployment.

Each track's own standalone service can also be run independently against its own port, for isolated testing:

| Track | Service | Default port |
|---|---|---|
| A — Deviation detection | `src/detection/api.py` | 8001 |
| B — Risk scoring | `src/risk_scoring/api.py` | 8002 |
| C — CAPA generation | `src/capa/api.py` | 8003 |
| D — Gateway (used by the frontend) | `src/backend/app/main.py` | 8000 |

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/psbalwani/bob-ai-hackathon-DOMinators.git
cd bob-ai-hackathon-DOMinators

# 2. Install Python dependencies (shared across all four tracks)
pip install -r requirements.txt

# 3. Install frontend dependencies
cd src/frontend
npm install
cd ../..

# 4. Generate the synthetic dataset every track builds/tests against
python src/data/generate_synthetic_data.py
```

## Running the Application

```bash
# Start the Track D gateway (from repo root)
uvicorn src.backend.app.main:app --reload --port 8000

# Start the frontend (in a separate terminal, from src/frontend)
cd src/frontend
npm run dev
```

The application is available at `http://localhost:5173` (frontend), gateway API at `http://localhost:8000`.

No Docker Compose / local Postgres setup is required — the gateway runs fully in-memory
without `DATABASE_URL` set. If you have a Neon connection string, set `DATABASE_URL` in
`src/.env` and the gateway will create its tables and persist there instead on next start.

## Running Tests

```bash
# All tracks, from repo root
pytest tests/ -v
```

Note: with real `WATSONX_API_KEY` credentials configured, `tests/test_api.py` and
`tests/test_capa.py` can be significantly slower (their `TestClient` triggers the app's
real startup path, which may make live watsonx.ai calls for ambiguous cases). This is a
known trade-off of testing against live credentials, not a bug — unset `WATSONX_API_KEY`
for a fast, fully deterministic test run if needed.

## Quick Demo

```bash
python src/data/generate_synthetic_data.py   # if you haven't already
uvicorn src.backend.app.main:app --reload --port 8000
# in a second terminal:
cd src/frontend && npm run dev
```

Then open `http://localhost:5173`. Recommended demo path: **Trial Overview** (ranked
sites) → click the highest-risk site → **Site Drill-down** (indicator breakdown,
deviation list, trend) → click a deviation → **Deviation Detail** (severity rationale +
protocol citation) → back to the site → open its **CAPA report** (root cause /
corrective / preventive action + evidence citations, exportable as Markdown).

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError` | Re-run `pip install -r requirements.txt` from repo root |
| `npm run dev` fails to reach the API | Confirm the gateway is running on port 8000 and CORS is enabled for `localhost:5173` (it is, by default, in `src/backend/app/main.py`) |
| `watsonx.ai` 401/403 error | Check `WATSONX_API_KEY` / `WATSONX_SPACE_ID` in `src/.env`; prefer `WATSONX_SPACE_ID` over `WATSONX_PROJECT_ID` (see table above) |
| Dashboard is empty on first load | The gateway runs the full pipeline once, lazily, on the first `/dashboard/summary` request — this can take longer than usual if real watsonx credentials are set (see the Tests note above); subsequent loads are fast since results are persisted |
| Data directory not found | Run `python src/data/generate_synthetic_data.py` from repo root first |
