# Synthetic Data Generator (Track C, hour 0-4)

`generate_synthetic_data.py` produces the full synthetic dataset every other
track builds and tests against, per the frozen contract in
[`docs/04_data_schema.md`](../../docs/04_data_schema.md). Stdlib-only, no
`pip install` required.

## Run it

```bash
python src/data/generate_synthetic_data.py
```

Writes to `data/synthetic/` (git-ignored — regenerate locally rather than
committing it; the default seed is fixed so the output is reproducible):

| File | Contents |
|---|---|
| `protocol.json` | The `TRIAL-2026-ONC-04` protocol spec (visit schedule, dosing rules, banned co-meds) plus `protocol_sections`: citable clause text for the RAG/citation layer. `protocol_sections` is an addition to the schema in `04_data_schema.md`, not a change to any existing field. |
| `sites.json` | 18 sites. Each carries `seed_risk_tier` (`high`/`medium`/`low`) and `seed_trend_intent` (`worsening`/`improving`/`stable`/`volatile`) — **generation-intent metadata only**, not the `risk_score`/`risk_band`/`trend` that Track B computes. Use it to sanity-check Track B's output tells the same story the data was seeded to tell, not as an input to the scoring model itself. |
| `patients.json` | ~250-300 patients distributed across sites. |
| `visit_records.json` / `.csv` | One row per patient x scheduled visit (`Patient Visit Record` shape). Every record starts fully protocol-compliant; a subset is then mutated to encode a deviation. |
| `seeded_deviations_ground_truth.json` / `.csv` | The ground-truth answer key: which `visit_record_id`s were deliberately broken, what type, and the **expected** severity + rationale + clause citation. Use this to score Track A's detector (recall/precision) and Track B's ranking. Field names mirror the `Deviation` object in `04_data_schema.md`, but use `seed_id`/`expected_severity` (not `deviation_id`/`severity`) so a seeded row can never collide with a detector-generated `DEV-xxxxxx` row. |
| `dataset_summary.md` | Human-readable counts: deviations by type/severity, and every site ranked by seeded deviation count — check this first to confirm the high/low-risk split still looks right after any regeneration. |

## Design notes

- **Only seeded deviations are true deviations.** All other records are
  fully compliant, so any extra flag from Track A's detector is a false
  positive — the dataset supports both recall and precision checks.
- **Severity mix is site-tier-driven, not random.** High-risk sites skew
  toward Major/frequent; low-risk sites skew toward Administrative/rare —
  see `docs/01_project_planning.md` section 8 ("3-5 clearly high-risk / 3-5
  clearly low-risk sites").
- **Trend is encoded via recency-weighted sampling**: `worsening` sites bias
  injected deviations toward the later visits (V5-V7); `improving` sites bias
  toward the earlier ones — gives Track B's trend calculation something real
  to detect.
- IDs stay fully synthetic (`PT-xxxxx`, `SITE-xxx`, `REC-xxxxxx`) — no real
  names or identifiers, per `04_data_schema.md` section 6.

## Regenerating with different scale

```bash
python src/data/generate_synthetic_data.py --seed 7 --min-patients-per-site 15 --max-patients-per-site 25
```

Any regeneration is deterministic for a given `--seed`. If you change the
default scale/counts, re-check `dataset_summary.md` to confirm the
high/low-risk sites are still visibly distinct — that's the property the
demo depends on.
