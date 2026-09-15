# Track B — Site Risk Scoring: Leading Indicators & Weighting

Design doc for `risk_score` (0-100) and its `indicator_breakdown`, matching the
`Site Risk Score` shape in `docs/04_data_schema.md` section 4 and the
`POST /risk-score/site` contract in `docs/05_api_contracts.md`.

## Why these five indicators

A score built on deviation *count* alone is gameable: a site running twice
the visit volume of another will rack up twice the deviations without being
riskier per patient, and a site with one Major safety deviation should not
rank below a site with ten Administrative paperwork slips. Each indicator
below exists to cancel out one specific way a naive count-based score would
mislead a risk manager:

| Indicator | Cancels out |
|---|---|
| `severity_mix_weight` | Treating a banned co-medication the same as a late visit |
| `deviation_frequency` | Penalizing high-volume sites just for having more visits |
| `repeat_offense_rate` | Missing systemic/training failures that look like "a few isolated events" in a raw count |
| `recency_weight` | Letting old, already-remediated deviations keep a site flagged forever |
| `trend_slope` | Missing a site that started clean and is getting worse (or crediting one that's already improving) |

## Indicator definitions (raw, each normalized to `[0, 1]` per site)

1. **`severity_mix_weight`** — severity-weighted deviation density.
   Each deviation contributes `Major=1.0`, `Minor=0.4`, `Administrative=0.1`.
   `raw = sum(severity_points) / total_visits`, capped at `1.0` via
   `min(raw / 0.5, 1.0)` (a site averaging ≥0.5 severity-points per visit
   maxes this indicator out).

2. **`deviation_frequency`** — volume, but rate-based so visit count cancels
   out. `raw = open_deviation_count / total_visits`, capped at `1.0` via
   `min(raw / 0.3, 1.0)` (≥30% of visits carrying an open deviation is
   already the worst case we expect to see).

3. **`repeat_offense_rate`** — systemic vs. isolated. Of the patients at this
   site who have *at least one* deviation, what fraction have *two or more*?
   `raw = patients_with_2plus_deviations / patients_with_1plus_deviations`
   (0 if no patient has any deviation). A high value means the same
   patients/visits keep failing — a process or training gap, not noise.

4. **`recency_weight`** — exponential recency decay, half-life 30 days from
   `computed_at`: each deviation contributes `0.5 ** (days_since_detected / 30)`.
   `raw = sum(recency_contributions) / total_visits`, capped at `1.0` via
   `min(raw / 0.3, 1.0)`. A site whose deviations are all months old scores
   near 0 here even if `deviation_frequency` is high — it's a historical
   problem, not an active one.

5. **`trend_slope`** — is the site getting worse or better *within the
   trial timeline*, independent of recency in wall-clock time. Bucket the
   site's visits by `scheduled_day` into first-half / second-half of the
   protocol's visit schedule; `raw = clamp((second_half_rate - first_half_rate) / 0.3, -1, 1)`
   then rescaled to `[0, 1]` via `(raw + 1) / 2` so 0.5 = flat, 1.0 = sharply
   worsening, 0.0 = sharply improving. (The categorical `trend` field —
   `worsening`/`stable`/`improving`/`volatile` — is derived separately, see
   below; it's a label for humans, this is the scoring input.)

## Weights (documented rationale — judging talking point)

| Indicator | Weight | Why this weight |
|---|---|---|
| `severity_mix_weight` | **0.35** | Highest — a single Major deviation (e.g. banned co-medication) is a direct patient-safety and audit-failure risk; severity should dominate over volume. |
| `deviation_frequency` | **0.25** | Volume still matters once it's rate-normalized — a site failing 1-in-4 visits is a different problem than 1-in-40. |
| `repeat_offense_rate` | **0.20** | A repeat-offense pattern is the strongest predictor of *why* a site fails an audit (training/process gap), so it outweighs simple recency or trend. |
| `recency_weight` | **0.10** | Active problems should nudge the score up, but shouldn't let a single old spike keep a now-clean site flagged. |
| `trend_slope` | **0.10** | Directionality is a useful early-warning signal but is the noisiest indicator at low visit counts, so it gets the smallest weight. |

Weights sum to 1.0.

## From raw indicators to `risk_score` and `indicator_breakdown`

```
contribution_i   = weight_i * raw_i
risk_score       = round(100 * sum(contribution_i))                 # 0-100
indicator_breakdown_i = contribution_i / sum(contribution_j)         # shares sum to 1.0
```

This matches the worked example in `04_data_schema.md` — the breakdown is
each indicator's *share of the score actually produced*, not the raw
indicator value or the static weight. That's what makes it explainable: a
risk manager reading `severity_mix_weight: 0.41` is told "41% of this site's
risk score comes from how severe its deviations are," which stays meaningful
even when `sum(raw_i)` is small (e.g. a low-risk site) because the shares
still sum to 1.0.

Edge case: if a site has zero deviations, all `contribution_i = 0`; report
`risk_score = 0` and `indicator_breakdown` as all zeros rather than dividing
by zero.

## `risk_band` thresholds

| Band | `risk_score` |
|---|---|
| High | ≥ 70 |
| Medium | 40–69 |
| Low | < 40 |

Chosen so that a site with one Major deviation and otherwise clean visits
(`severity_mix_weight` raw ≈ 1.0 alone contributing `35` points) doesn't
automatically land in "High" by itself — it takes either a severe deviation
*plus* another indicator, or a sustained pattern across several indicators,
to cross 70. This avoids the score being dominated by a single outlier event
while still keeping severity the largest single lever.

## Sanity-check targets (against the seeded synthetic data)

Per `data/synthetic/dataset_summary.md`, `SITE-018/013/011/017/003` are
`seed_risk_tier: high` and `SITE-005/008` (0 seeded deviations) are `low`.
The model is considered directionally correct if, on the real seeded
dataset, the high-tier sites land in the top 5 of the ranking and the
zero-deviation sites land at `risk_score: 0` / `Low`. This is a smoke test,
not a ground-truth label — `seed_risk_tier` is generation-intent metadata,
never a scoring input (see `src/data/README.md`).

## Next steps (subsequent tasks, not yet implemented)

- `scoring.py` — implement the five raw indicators + weighting above.
- `trend.py` — derive the categorical `trend` label (`worsening` / `stable`
  / `improving` / `volatile`) from the same visit-schedule bucketing.
- `api.py` — `POST /risk-score/site`, `GET /risk-score/site/{site_id}`,
  `GET /risk-score/ranking`.
- `tests/` — high-risk site, low-risk site, and the "few visits, one Major
  deviation" edge case called out in `docs/03_team_division.md`.
