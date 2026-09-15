# Source Code

One module per track (see `docs/03_team_division.md`), plus the frontend:

```
src/
  data/            ← Track C: synthetic dataset generator + ICH E6(R2) corpus
  detection/       ← Track A: deviation detection & severity classification
  risk_scoring/    ← Track B: site-level risk scoring
  capa/            ← Track C: CAPA report generation
  backend/         ← Track D: gateway that orchestrates the four modules above
                     (in-process, not HTTP proxying) and serves the dashboard
  frontend/        ← Track D: React + Vite + Tailwind dashboard
  .env.example     ← Copy to .env and fill in (see docs/setup-guide.md)
```

Each of `detection/`, `risk_scoring/`, and `capa/` also exposes its own small
standalone FastAPI service (ports 8001-8003) for isolated testing, independent of the
gateway in `backend/` (port 8000) that the frontend actually talks to — see each
module's own `README.md` and `docs/setup-guide.md` for exact run commands.

## Important Files

- `requirements.txt` (repo root) — shared Python dependency manifest for all four tracks
- `src/frontend/package.json` — frontend dependencies
- `.env.example` (this directory) / `src/frontend/.env.example` — environment variable templates (NEVER commit the real `.env`)

## What NOT to Include in src/

- `.env` files with real secrets
- `node_modules/`, `.venv/`, `__pycache__/`, `dist/`, `build/` (already in `.gitignore`)
