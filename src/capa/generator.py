"""Orchestrates templates.py + corpus.py (+ optionally llm_hook.py) into a
CapaReport for either a single deviation or a site-level cluster.

Design (see DESIGN.md for the full rationale):
  1. `evidence_citations` is built ENTIRELY from structural lookups over real
     data (each deviation's own `protocol_clause_ref` -- already validated
     non-hallucinated by Track A's severity.py -- plus corpus-verified ICH
     chunks). The LLM is never involved in producing citations, so this
     field cannot be hallucinated regardless of whether watsonx.ai is
     configured.
  2. The narrative fields (root_cause/corrective_action/preventive_action)
     start from templates.py's deterministic baseline (always available,
     grounded in the protocol's own dosing rules + the deviation type/
     severity). If watsonx.ai is configured and available, llm_hook.py may
     refine that baseline into more specific prose -- if that call fails or
     returns anything unparseable, the deterministic baseline is used
     unchanged. Either way the report is fully populated and grounded.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from . import corpus, llm_hook, templates
from .models import CapaReport

GENERATOR_VERSION = "capa-gen-v1"


def _dominant_type(deviations: list[dict]) -> str:
    counts = Counter(d["type"] for d in deviations)
    best_count = max(counts.values())
    # tie-break by first appearance, for deterministic output
    for d in deviations:
        if counts[d["type"]] == best_count:
            return d["type"]
    raise AssertionError("unreachable")  # pragma: no cover


def _worst_severity_for_type(deviations: list[dict], dev_type: str) -> str:
    severities = [d["severity"] for d in deviations if d["type"] == dev_type]
    return templates.worst_severity(severities)


def generate(
    scope: str,
    deviations: list[dict],
    protocol: dict,
    ich_corpus: dict[str, dict],
    capa_id: str,
    generated_at: str | None = None,
) -> CapaReport:
    """Build a CapaReport from an already-resolved list of Deviation-shaped dicts.

    `deviations` must be non-empty and all share the same `site_id`. For
    scope="deviation" it must contain exactly one deviation.
    """
    if scope not in ("deviation", "site"):
        raise ValueError(f"unknown scope: {scope}")
    if not deviations:
        raise ValueError("generate() requires at least one deviation")
    if scope == "deviation" and len(deviations) != 1:
        raise ValueError("scope='deviation' requires exactly one deviation")

    site_id = deviations[0]["site_id"]
    if any(d["site_id"] != site_id for d in deviations):
        raise ValueError("all deviations in a CAPA report must share one site_id")

    overall_severity = templates.worst_severity([d["severity"] for d in deviations])
    type_counts = Counter(d["type"] for d in deviations)
    # dict.fromkeys (not a set) preserves first-seen order for tied counts,
    # matching _dominant_type's own tie-break rule -- a plain set's iteration
    # order for strings is hash-randomized per process and would otherwise
    # make the numbered action list (and evidence_citations order) shuffle
    # between runs on identical input.
    distinct_types = sorted(dict.fromkeys(d["type"] for d in deviations), key=lambda t: -type_counts[t])

    action_sets = {
        t: templates.for_deviation_type(t, _worst_severity_for_type(deviations, t), site_id, protocol)
        for t in distinct_types
    }
    dominant_type = _dominant_type(deviations)
    dominant_actions = action_sets[dominant_type]

    if len(distinct_types) == 1:
        root_cause = dominant_actions.root_cause
        if type_counts[dominant_type] > 1:
            root_cause += f" This occurred {type_counts[dominant_type]} times across the reviewed visits."
        corrective_action = dominant_actions.corrective_action
        preventive_action = dominant_actions.preventive_action
    else:
        mix = ", ".join(f"{t} x{type_counts[t]}" for t in distinct_types)
        root_cause = (
            f"{site_id} shows a cluster of {len(deviations)} protocol deviations "
            f"across {len(distinct_types)} categories in the reviewed period ({mix}). "
            f"The most frequent pattern is {dominant_type} "
            f"({type_counts[dominant_type]} occurrence(s)): {dominant_actions.root_cause}"
        )
        corrective_action = " ".join(
            f"{i+1}. {action_sets[t].corrective_action}" for i, t in enumerate(distinct_types)
        )
        preventive_action = " ".join(
            f"{i+1}. {action_sets[t].preventive_action}" for i, t in enumerate(distinct_types)
        )

    # LLM refinement is optional and additive: grounded in the same baseline
    # text plus real clause/ICH text, dominant-type only (keeps the prompt
    # small and unambiguous). Falls back to the baseline above on any issue.
    dominant_rationales = [d["severity_rationale"] for d in deviations if d["type"] == dominant_type]
    ich_chunks = corpus.ich_chunks_for_deviation(ich_corpus, dominant_type, _worst_severity_for_type(deviations, dominant_type))
    clause_texts = dominant_rationales[:1] + [c["text"] for c in ich_chunks]

    llm_draft = llm_hook.draft_capa_text(
        site_id=site_id,
        deviation_type=dominant_type,
        severity=overall_severity,
        deviation_count=len(deviations),
        clause_texts=clause_texts,
        baseline_root_cause=root_cause,
        baseline_corrective_action=corrective_action,
        baseline_preventive_action=preventive_action,
    )
    if llm_draft is not None:
        root_cause = llm_draft["root_cause"]
        corrective_action = llm_draft["corrective_action"]
        preventive_action = llm_draft["preventive_action"]

    # Evidence citations: built structurally, never from the LLM. Every
    # protocol clause ref comes verbatim from a real Deviation object;
    # every ICH citation comes from corpus.py's corpus-verified lookup.
    citations: list[str] = []
    for d in deviations:
        citations.append(d["deviation_id"])
    for ref in dict.fromkeys(d["protocol_clause_ref"] for d in deviations):  # dedup, keep order
        citations.append(ref)
    ich_seen: set[str] = set()
    for t in distinct_types:
        for chunk in corpus.ich_chunks_for_deviation(ich_corpus, t, _worst_severity_for_type(deviations, t)):
            citation = corpus.ich_citation_string(chunk)
            if citation not in ich_seen:
                ich_seen.add(citation)
                citations.append(citation)

    return CapaReport(
        capa_id=capa_id,
        scope=scope,
        site_id=site_id,
        related_deviation_ids=[d["deviation_id"] for d in deviations],
        root_cause=root_cause,
        corrective_action=corrective_action,
        preventive_action=preventive_action,
        suggested_owner_role=templates.OWNER_ROLE_BY_SEVERITY[overall_severity],
        suggested_due_window_days=templates.DUE_WINDOW_DAYS_BY_SEVERITY[overall_severity],
        generated_at=generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        evidence_citations=citations,
        protocol_id=deviations[0].get("protocol_id", ""),
    )
