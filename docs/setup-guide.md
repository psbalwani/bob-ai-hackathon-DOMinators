# Setup Guide

> **This file is read by the automated evaluation pipeline. Be precise and complete.**
>
> This guide reflects the planned setup per [`docs/architecture.md`](architecture.md) (`src/backend` = FastAPI, `src/frontend` = React, PostgreSQL, Docker Compose). Update the exact commands here once the corresponding code lands in `src/`.

## Prerequisites

Before you begin, ensure you have the following installed:

- [ ] Python 3.11+
- [ ] Node.js 18+
- [ ] Docker Desktop
- [ ] An IBM Cloud account with watsonx.ai access

## Environment Variables

Copy `src/.env.example` to `src/.env` and fill in the values:

```bash
cp src/.env.example src/.env
```

| Variable | Description | Required |
|---|---|---|
| `WATSONX_API_KEY` | IBM watsonx.ai API key (deviation judgment, severity rationale, CAPA generation) | Yes |
| `WATSONX_PROJECT_ID` | watsonx.ai project ID | Yes |
| `WATSONX_URL` | watsonx.ai region endpoint | Yes |
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `APP_PORT` | Backend API port | No (default `8000`) |

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/psbalwani/bob-ai-hackathon-DOMinators.git
cd bob-ai-hackathon-DOMinators

# 2. Install backend dependencies
cd src/backend
pip install -r requirements.txt

# 3. Install frontend dependencies
cd ../frontend
npm install

# 4. Set up the database
docker compose up -d db
# then run migrations, e.g.:
# alembic upgrade head
```

## Running the Application

```bash
# Start the backend (from src/backend)
uvicorn app.main:app --reload --port 8000

# Start the frontend (in a separate terminal, from src/frontend)
npm run dev
```

The application will be available at: `http://localhost:5173` (frontend), API at `http://localhost:8000`.

Or, to bring up the full stack (Postgres + backend + frontend) at once:

```bash
docker compose up
```

## Running Tests

```bash
# Backend
cd src/backend
pytest tests/ -v

# Deviation-detection recall / seeded test cases
pytest tests/test_deviation_detection.py -v
```

## Quick Demo (Optional)

```bash
python src/backend/scripts/seed_demo_data.py   # loads the synthetic protocol + visit dataset
open http://localhost:5173
```

Recommended demo path: Trial Overview → highest-risk Site Drill-down → a single Deviation Detail (severity + protocol citation) → generate/open the CAPA report for that site.

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError` | Re-run `pip install -r requirements.txt` inside `src/backend` |
| Database connection refused | Ensure PostgreSQL is running: `docker compose up -d db` |
| `watsonx.ai` 401 error | Check `WATSONX_API_KEY` / `WATSONX_PROJECT_ID` in `src/.env` |
| Frontend can't reach API | Confirm the backend is running on the port set in `APP_PORT` and CORS is enabled for `localhost:5173` |
