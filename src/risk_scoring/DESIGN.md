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
   `min(raw / 0.08, 1.0)` — a site averaging ≥0.08 severity-points per visit
   (e.g. roughly one Major deviation every ~12 visits, sustained) is already
   a serious outlier for a trial at this project's scale.

2. **`deviation_frequency`** — volume, but rate-based so visit count cancels
   out. `raw = open_deviation_count / total_visits`, capped at `1.0` via
   `min(raw / 0.10, 1.0)` — ≥10% of visits carrying an open deviation is
   already the worst case we expect to see at this trial scale.

3. **`repeat_offense_rate`** — systemic vs. isolated. Of the patients at this
   site who have *at least one* deviation, what fraction have *two or more*?
   `raw = patients_with_2plus_deviations / patients_with_1plus_deviations`
   (0 if no patient has any deviation). A high value means the same
   patients/visits keep failing — a process or training gap, not noise.

4. **`recency_weight`** — exponential recency decay, half-life 30 days from
   the site's own most recent visit date (`as_of`): each deviation
   contributes `0.5 ** (days_since_detected / 30)`.
   `raw = sum(recency_contributions) / total_visits`, capped at `1.0` via
   `min(raw / 0.01, 1.0)`. A site whose deviations are all months old scores
   near 0 here even if `deviation_frequency` is high — it's a historical
   problem, not an active one. If a site has zero deviations, this (and
   every other indicator) is `0`, not `0.5` — see the zero-deviation edge
   case below.

5. **`trend_slope`** — is the site getting worse or better *within the
   trial timeline*, independent of recency in wall-clock time. Bucket the
   site's visits by `scheduled_day` into first-half / second-half of the
   protocol's visit schedule; `raw = clamp((second_half_rate - first_half_rate) / 0.15, -1, 1)`
   then rescaled to `[0, 1]` via `(raw + 1) / 2` so 0.5 = flat, 1.0 = sharply
   worsening, 0.0 = sharply improving. (The categorical `trend` field —
   `worsening`/`stable`/`improving`/`volatile` — is derived separately, see
   below; it's a label for humans, this is the scoring input.) This is the
   noisiest indicator at low per-site deviation counts (a handful of
   deviations landing in one bucket by chance can flip the sign) — that's
   exactly why it carries the lowest weight, and why the categorical label
   gets a more careful treatment in the dedicated trend-calculation task
   rather than being trusted as-is here.

**Calibration note:** the three cap constants above (`0.08`, `0.10`, `0.01`)
were set by measuring the actual achievable range on the real generated
dataset (`data/synthetic/`, 18 sites / 2023 visits / 52 seeded deviations)
so that the worst real site lands near saturation on each indicator, rather
than picked abstractly. If the dataset's scale or deviation prevalence
changes materially (e.g. a much larger or much noisier regeneration),
re-check these against `python -m src.risk_scoring.scoring` output before
trusting the resulting `risk_band` split.

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

Chosen so that a single low-volume site with one Major deviation (e.g. 12 or
fewer visits, where `severity_mix_weight` alone saturates and contributes
`35` points) doesn't automatically land in "High" by itself — it takes
either a severe deviation *plus* another indicator, or a sustained pattern
across several indicators, to cross 70. This avoids the score being
dominated by a single outlier event while still keeping severity the
largest single lever.

## Sanity-check targets (against the seeded synthetic data) — verified

Per `data/synthetic/dataset_summary.md`, `SITE-018/013/011/017/003` are
`seed_risk_tier: high` and `SITE-005/008` (0 seeded deviations) are `low`.
The model is directionally correct if, on the real seeded dataset, the
high-tier sites land in the top 5 of the ranking and the zero-deviation
sites land at `risk_score: 0` / `Low`. This is a smoke test, not a
ground-truth label — `seed_risk_tier` is generation-intent metadata, never
a scoring input (see `src/data/README.md`).

Verified via `python -m src.risk_scoring.scoring --data-dir data/synthetic`
(seed 42 dataset): the top 5 by `risk_score` are exactly
`SITE-013 (79, High) > SITE-018 (53, Medium) > SITE-017 (50, Medium) >
SITE-011 (42, Medium) > SITE-003 (34, Low)` — i.e. all 5 seeded high-tier
sites, in that order, above every medium/low-tier site — and both
zero-deviation sites (`SITE-005`, `SITE-008`) score exactly `0`. `SITE-003`
lands just under the Medium threshold despite its `high` seed tier because
its 6 deviations are diluted across 133 visits (a 4.5% rate, the lowest of
the five) — the model is reporting genuine relative severity, not just
echoing the seed label, which is the intended behavior.

## Drug-Level Aggregation — FDA Approval Readiness (stretch feature)

`drug_aggregate.py` rolls up every site's `RiskScore` for a drug, plus that
drug's deviations and CAPA remediation status, into one `DrugPerformance`
object (`docs/04_data_schema.md` section 7): a single `drug_risk_index`
(0-100, same direction as `risk_score`) and a `readiness_band` a
regulatory-affairs/trial-sponsor reader can act on without opening every
site individually. This does not re-score sites — it aggregates outputs
Track A/B/C already produce, at one more level of rollup than
`pipeline.dashboard_summary` (which lists sites; this collapses them into
one verdict).

### Why these five factors

| Factor | Weight | Why |
|---|---|---|
| `avg_site_risk` | **0.35** | The overall exposure level across the network — if the average site is already risky, no other factor should be able to paper over that. |
| `high_risk_site_share` | **0.25** | Breadth matters independently of average: one severe outlier averaged against many clean sites can look deceptively okay, so the *fraction* of sites in the High band is tracked separately. |
| `major_deviation_rate` | **0.20** | The rate (not count) of Major/patient-safety deviations across every visit in the drug's network — the single factor that maps most directly to what an FDA inspection is actually looking for. |
| `unresolved_capa_rate` | **0.10** | Whether known issues are being remediated. A drug with real problems but fully-approved CAPAs in flight is in a meaningfully better position than one where remediation is stalled or rejected — this is what separates "problem exists" from "problem is uncontrolled." |
| `trend_pressure` | **0.10** | Net directional signal — more sites trending worse than better says the situation is compounding, not just present. Lowest weight because `trend` is already the noisiest per-site label (see above). |

Weights sum to 1.0. When the caller has no CAPA visibility (`capa_reports=None`
— Track B's own standalone service, which has no CAPA data), the
`unresolved_capa_rate` factor is dropped entirely and its weight
redistributed proportionally across the other four, rather than treated as
`0` (which would silently read as "every issue already resolved" instead of
"unknown"). See `test_missing_capa_data_is_not_treated_as_zero_risk` in
`tests/test_drug_aggregate.py`.

### From raw factors to `drug_risk_index`

Same shape as the site-level model: `contribution_i = weight_i * raw_i`,
`drug_risk_index = round(100 * sum(contribution_i))`, `factor_breakdown_i =
contribution_i / sum(contribution_j)`. `major_deviation_rate`'s raw value is
capped via `min(raw / 0.015, 1.0)` — calibrated the same way as
`indicators.py`'s caps, by measuring the actual Major-deviation rate across
the real 10-drug portfolio (`data/synthetic/` + `data/synthetic/drugs/*`,
range 0.006–0.015) rather than picked abstractly.

### `readiness_band` thresholds

| Band | `drug_risk_index` |
|---|---|
| High Risk of Rejection | ≥ 55 |
| Conditional — Remediation Required | 25–54 |
| Likely Approval Ready | < 25 |

### Sanity-check against the real 10-drug portfolio — verified

Run via `python -m src.risk_scoring.drug_aggregate --data-dir data/synthetic`
(and the sibling `data/synthetic/drugs/*` datasets): across all 10 drugs the
index ranges 18–37, with the 4 drugs that have at least one High-risk site
or an above-median Major-deviation rate landing in "Conditional", and the
other 6 in "Likely Approval Ready" — none of the demo-scale drugs are
severely broken enough to hit "High Risk of Rejection", which matches
reality (this dataset was built to make *site-level* risk visibly
differentiated, not to seed a catastrophic drug). The hand-built fixtures in
`tests/test_drug_aggregate.py` cover the "High Risk of Rejection" case
directly (a drug with a saturated Major-deviation rate, majority-High sites,
and mostly-rejected CAPAs).

### Implementation status

- ✅ `drug_aggregate.py` — `compute_drug_performance`, weighting, factor
  breakdown, deterministic (never LLM-generated, never able to cite a
  number not already in the aggregated stats) rationale sentences, plus a
  CLI for the sanity check above.
- ✅ `tests/test_drug_aggregate.py` — a clearly approval-ready drug, a
  clearly high-risk drug, the missing-CAPA-data redistribution behavior,
  the zero-sites edge case, and a check that rationale text never cites a
  number that doesn't match the aggregated stats. All 5 pass.
- ✅ Wired into Track D's gateway at `GET /dashboard/drug-performance`
  (`src/backend/app/pipeline.py::drug_performance_summary`, `src/backend/app/main.py`)
  using real persisted risk scores/deviations/CAPA review statuses, and into
  this module's own standalone service at `GET /risk-score/drug-summary`
  (`api.py`, without CAPA data). Frontend: `src/frontend/src/pages/DrugPerformance.tsx`,
  a new "Drug Performance" tab in the sidebar.

## Implementation status

- ✅ `loaders.py` — loads protocol/sites/visit records; adapts Track C's
  seeded ground truth into `Deviation`-shaped dicts until Track A's real
  `POST /deviations/detect` output is available.
- ✅ `indicators.py` — the five raw indicator functions above.
- ✅ `scoring.py` — weighting, `risk_score`/`indicator_breakdown`/`risk_band`
  assembly, `compute_site_risk_score` / `rank_sites`, plus a CLI for the
  sanity check above.
- ✅ `trend.py` — categorical `trend` label (`worsening` / `stable` /
  `improving` / `volatile`) via an early/mid/late tercile comparison with a
  calibrated noise threshold, wired into `scoring.py`. Verified against the
  real dataset's `seed_trend_intent`: 12/17 sites with any deviations match
  (10/11 `stable` correct, 2/3 `worsening` correct, 0/2 `volatile` correct —
  volatile detection is the known weak point at this sample size, documented
  in `trend.py`'s module docstring rather than papered over).
- ✅ `api.py` — standalone FastAPI service exposing `POST /risk-score/site`,
  `GET /risk-score/site/{site_id}`, `GET /risk-score/ranking`, per
  `docs/05_api_contracts.md` (including its error convention). Run it with:
  ```
  pip install -r src/risk_scoring/requirements.txt
  uvicorn src.risk_scoring.api:app --reload --port 8002
  ```
  This is Track B's own early stub per `docs/03_team_division.md` ("expose
  the module as its own small FastAPI endpoint early"), not Track D's
  unified gateway (`src/backend` in `docs/setup-guide.md`) — Track D
  proxies to this until integration.
- ✅ `tests/test_risk_scoring.py` (top-level `tests/`, matching Track A's
  convention) — hand-built fixtures (not the generated dataset, so expected
  numbers are exactly derivable): a clearly high-risk site (every indicator
  saturated -> `risk_score == 100`), a clearly low-risk site, the
  zero-deviation edge case, and the rate-vs-raw-count edge case — a 2-visit
  site and a 200-visit site each with exactly one identical Major
  deviation score `70/High` vs `9/Low` respectively, proving the model
  rate-normalizes rather than counting raw deviations. All 4 pass
  (`pytest tests/test_risk_scoring.py -v`).
