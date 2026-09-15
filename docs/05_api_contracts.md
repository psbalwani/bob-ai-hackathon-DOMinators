# API Contracts — Shared Interface Between Tracks

Purpose: let Tracks A, B, C build and test independently, and let Track D integrate them without renegotiating shapes mid-hackathon. Each track should expose its own module behind these endpoints *itself* early on (even a rough stub), so Track D can point at it from hour 4 onward instead of waiting.

All request/response bodies use the objects defined in `04_data_schema.md`. Auth: a single shared API key header (`X-API-Key`) is enough for a hackathon demo — do not spend time on real auth.

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

---

## Track C — CAPA Generation

### `POST /capa/generate`
Generates a CAPA report for a deviation or a site cluster.

**Request**
```json
{ "scope": "site", "site_id": "SITE-017", "deviation_ids": ["DEV-000456", "DEV-000461"] }
```
*(`scope` can be `"deviation"` for a single deviation, or `"site"` for a clustered report)*

**Response:** a `CapaReport` object (see `04_data_schema.md`).

### `GET /capa/{capa_id}`
Returns a previously generated report.

### `GET /capa/{capa_id}/export?format=pdf|markdown`
Returns the report formatted for export.

---

## Track D — Orchestration / Dashboard Aggregation

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

---

## Error Convention (all endpoints)

```json
{ "error": { "code": "VALIDATION_ERROR", "message": "protocol_id not found" } }
```
Standard HTTP status codes: `400` validation, `404` not found, `500` unexpected. Keep it this simple — don't build a bespoke error framework during the hackathon.

## Versioning

Not needed for the hackathon — single version, breaking changes announced in the team channel and updated here immediately (this file is the source of truth, keep it in sync with what's actually built).
