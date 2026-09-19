# API Contracts — Shared Interface Between Tracks

Purpose: let Tracks A, B, C build and test independently, and let Track D integrate them without renegotiating shapes mid-hackathon. Each track should expose its own module behind these endpoints *itself* early on (even a rough stub), so Track D can point at it from hour 4 onward instead of waiting.

All request/response bodies use the objects defined in `04_data_schema.md`.

**Auth (post-freeze update):** the original plan was a single shared `X-API-Key` header ("don't spend time on real auth"). That changed once the platform grew to 10 separate drug trials that must not see each other's data: Track D's gateway (`src/backend/app/main.py`) now requires a bearer token from `POST /auth/login` (see below) on every request, and 403s any request for a `protocol_id` the caller doesn't own. This only applies to the integrated gateway — Tracks A/B/C's own standalone dev services (ports 8001–8003) are unaffected and still single-dataset, unauthenticated dev tools.

### `POST /auth/login`
**Request:** `{ "username": "...", "password": "..." }`
**Response:** `{ "access_token": "...", "token_type": "bearer", "user": { "user_id", "username", "protocols": [{"protocol_id","title","drug"}, ...] } }`
Send the token back as `Authorization: Bearer <access_token>` on every subsequent request.

### `GET /auth/me`
Returns the same `user` shape as login, for restoring a session (e.g. after a page refresh) without re-prompting for a password.

---

## Track A — Deviation Detection

### `POST /deviations/detect`
Detects and classifies deviations for a given set of visit records against a protocol.

**Request**
```json
{
  "protocol_id": "TRIAL-2026-ONC-04",
  "visit_record_ids": ["REC-000123", "REC-000124"]
}
```
*(omit `visit_record_ids` to run against all visits for the protocol)*

**Response**
```json
{
  "deviations": [ /* array of Deviation objects, see 04_data_schema.md */ ]
}
```

### `GET /deviations/site/{site_id}`
Returns all known deviations for a site.

**Response:** `{ "deviations": [ ... ] }`

---

## Track B — Site Risk Scoring

### `POST /risk-score/site`
Computes (or recomputes) the risk score for a site.

**Request**
```json
{ "site_id": "SITE-017", "protocol_id": "TRIAL-2026-ONC-04" }
```

**Response:** a `RiskScore` object (see `04_data_schema.md`).

### `GET /risk-score/site/{site_id}`
Returns the latest computed score for a site.

### `GET /risk-score/ranking?protocol_id=...`
Returns all sites for a protocol, ranked by `risk_score` descending.

**Response**
```json
{ "sites": [ { "site_id": "SITE-017", "risk_score": 78, "risk_band": "High" }, ... ] }
```

### `GET /risk-score/drug-summary?protocol_id=...` *(post-freeze addition, stretch feature)*
Track B's own standalone-service version of drug-level aggregation (see `GET /dashboard/drug-performance` under Track D below, which is what the dashboard actually calls). Same computation, minus the CAPA-remediation factor — this service has no CAPA data, so `unresolved_capa_rate` is dropped and its weight redistributed (see `src/risk_scoring/drug_aggregate.py`).

**Response:** a `DrugPerformance` object (see `04_data_schema.md` section 7) with `capa_summary: null`.

---

## Track C — CAPA Generation

### `POST /capa/generate`
Generates a CAPA report for a deviation or a site cluster.

**Request** (Track D gateway; `protocol_id` required now that a `site_id` alone is ambiguous across shared-site protocols — Track C's own standalone service at port 8003 still only takes `scope`/`site_id`/`deviation_ids`, since its dataset is always single-protocol)
```json
{ "protocol_id": "TRIAL-2026-ONC-04", "scope": "site", "site_id": "SITE-017", "deviation_ids": ["DEV-000456", "DEV-000461"] }
```
*(`scope` can be `"deviation"` for a single deviation, or `"site"` for a clustered report)*

**Response:** a `CapaReport` object (see `04_data_schema.md`).

### `GET /capa/{capa_id}`
Returns a previously generated report.

### `GET /capa/{capa_id}/export?format=pdf|markdown`
Returns the report formatted for export.

---

## Track D — Orchestration / Dashboard Aggregation

**Multi-drug (post-freeze):** every route below requires the `Authorization: Bearer` token from `POST /auth/login` and, on any route keyed only by `site_id`/`deviation_id`/`capa_id`, resolves or requires `protocol_id` and 403s if the caller doesn't own it (see the Auth section above and `src/backend/app/main.py`).

### `POST /pipeline/run`
Runs the full pipeline for a protocol: detect → score → generate CAPA for high-risk sites. Used to (re)populate the dashboard.

**Request:** `{ "protocol_id": "TRIAL-2026-ONC-04" }`

**Response:** `{ "status": "completed", "sites_processed": 18, "deviations_found": 142, "capa_reports_generated": 6 }`

### `GET /dashboard/summary?protocol_id=...`
Aggregated view for the Trial Overview screen.

**Response**
```json
{
  "protocol_id": "TRIAL-2026-ONC-04",
  "total_sites": 18,
  "total_patients": 260,
  "total_visits": 3120,
  "open_deviations": 142,
  "high_risk_sites": 5,
  "site_ranking": [ { "site_id": "SITE-017", "risk_score": 78, "risk_band": "High" }, ... ]
}
```

### `GET /dashboard/drug-performance?protocol_id=...` *(post-freeze addition, stretch feature)*
Drug-level aggregation across every site under the protocol — the single-number, single-verdict view for a regulatory-affairs / trial-sponsor audience ("would this drug's site network pass an FDA inspection right now"), backing the dashboard's Drug Performance page. Rolls up Track B's persisted site risk scores, Track A's deviations, and Track C's CAPA review statuses; computation lives in `src/risk_scoring/drug_aggregate.py` (Track B), wired here the same way `dashboard_summary` wires `rank_sites`.

**Response:** a `DrugPerformance` object (see `04_data_schema.md` section 7).

---

## Error Convention (all endpoints)

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "protocol_id not found" } }
```
Standard HTTP status codes: `400` validation, `404` not found, `500` unexpected. Keep it this simple — don't build a bespoke error framework during the hackathon.

## Versioning

Not needed for the hackathon — single version, breaking changes announced in the team channel and updated here immediately (this file is the source of truth, keep it in sync with what's actually built).
