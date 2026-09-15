# CAPA Generator — Design Notes (Track C)

## Why citations can't be hallucinated (the checklist's explicit requirement)

`evidence_citations` is built **structurally**, never by the LLM:

1. Every `deviation_id` in the report comes from a real, resolved `Deviation`
   object (Track A's actual detector output, or a specific id the caller
   asked for — both cases 404 if the id doesn't exist).
2. Every protocol clause citation is that deviation's own
   `protocol_clause_ref` field, verbatim. Track A's `severity.py` already
   resolves that against `protocol["protocol_sections"]` when the deviation
   was detected — by the time it reaches this module, it's already a real
   section, not something this module invents.
3. Every ICH citation comes from `corpus.py`'s `(type, severity) -> chunk_id`
   lookup table, resolved against the actually-loaded
   `src/data/ich_e6r2/guideline_chunks.json` — a `chunk_id` that isn't in the
   loaded corpus is silently dropped rather than cited.

The LLM (`llm_hook.py`), when configured, only ever rewrites the *prose* of
`root_cause` / `corrective_action` / `preventive_action` — it never touches
`evidence_citations`. So even in the worst case (a bad watsonx.ai response),
the report's citations stay exactly as grounded as they'd be with no LLM
involved at all. `tests/test_capa.py` checks this directly: it verifies
every citation string traces back to real data, independent of which code
path (LLM or template) produced the narrative text.

## Why there's always a deterministic fallback

Same resilience contract as Track A's `llm_hook.py`: `draft_capa_text()`
returns `None` on missing credentials, a missing SDK, an API failure, or an
unparseable response — for any of those, `generator.py` keeps the
`templates.py` baseline text unchanged. The endpoint therefore always
returns a complete, grounded report, with or without watsonx.ai configured.
This matters for the demo: a network hiccup or an unset API key during a
live run must not break CAPA generation.

## Owner role / due-window policy

Both are driven by the **worst severity among the related deviations** —
one Major deviation in an otherwise-Minor cluster still requires PI-level,
7-day attention, since GCP risk is about the worst finding, not the average
one:

| Severity | Suggested owner | Due window |
|---|---|---|
| Major | Site Principal Investigator | 7 days |
| Minor | Clinical Research Associate (CRA) | 14 days |
| Administrative | Site Coordinator | 21 days |

## Site-level clustering

A site-scope report with multiple deviation *types* doesn't just describe
the most frequent one and ignore the rest: `root_cause` names the full type
mix and count, then narrates the dominant pattern in detail; corrective and
preventive actions are the union of every distinct type's action (each
deduplicated once), numbered, so the report addresses every category of
issue actually present at the site, not just the loudest one.

## What's intentionally out of scope for the hackathon

- Risk-score context (Track B's `RiskScore`) isn't folded into the CAPA
  content itself — the `CapaReport` contract in `04_data_schema.md` doesn't
  carry risk fields, and severity alone already drives urgency. The
  dashboard (Track D) is expected to show a CAPA next to its site's risk
  score, not merge them into one object.
- True semantic retrieval (embeddings + a vector DB) over the ICH corpus —
  the `(type, severity) -> chunk_id` lookup in `corpus.py` is a deterministic
  table, not a similarity search. It's accurate for this trial's fixed set
  of 5 deviation types, and — unlike a similarity search — it can never
  retrieve the wrong chunk. A real vector store (per `docs/architecture.md`)
  would matter more once deviation types/ambiguity grow beyond this fixed
  set.
