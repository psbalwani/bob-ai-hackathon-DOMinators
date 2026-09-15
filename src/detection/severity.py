"""Severity classification + clause citation for a rules.Finding.

Every deviation type is deterministic except late_visit's boundary band,
which optionally consults llm_hook.py and otherwise falls back to a fixed,
conservative default -- see the module docstring there for why.
"""

from __future__ import annotations

from . import llm_hook, retrieval
from .rules import Finding

# Fixed query for the one ambiguous case (see below) -- deliberately phrased
# to match how the ICH-TAXONOMY-MINOR / ICH-TAXONOMY-ADMINISTRATIVE chunks
# describe this exact boundary ("late_visit ... outside ... window").
_LATE_VISIT_AMBIGUOUS_QUERY = (
    "late visit outside protocol window severity minor or administrative "
    "documentation lapse"
)

CLAUSE_SECTION_FOR_TYPE = {
    "missed_visit": "3.1",
    "late_visit": "3.1",
    "dosage_out_of_range": "4.1",
    "banned_comedication": "4.2",
    "missing_procedure": "5.1",
    "other": "3.1",  # BUG-01: fallback section for the generic "other" deviation type
}

# Deterministic missing_procedure severity by which procedure is missing.
_MISSING_PROCEDURE_SEVERITY = {
    "informed_consent": "Major",
    "vitals": "Administrative",
}
_MISSING_PROCEDURE_DEFAULT_SEVERITY = "Minor"  # blood_draw, dosing, ecg, imaging

# Late-visit boundary: <=1 extra day is Administrative, >=4 is Minor,
# 2-3 extra days is the genuinely ambiguous band handed to llm_hook.
_LATE_VISIT_ADMIN_MAX_EXTRA_DAYS = 1
_LATE_VISIT_MINOR_MIN_EXTRA_DAYS = 4


def _clause_text(protocol: dict, section_id: str) -> tuple[str, str]:
    """Return (clause_ref, full_text) for a protocol_sections entry."""
    section = next(s for s in protocol["protocol_sections"] if s["section_id"] == section_id)
    return f"Section {section['section_id']} - {section['title']}", section["text"]


def classify(protocol: dict, record: dict, finding: Finding) -> tuple[str, str, str]:
    """Return (severity, rationale, protocol_clause_ref) for one Finding."""
    clause_ref, clause_text = _clause_text(protocol, CLAUSE_SECTION_FOR_TYPE[finding.type])

    if finding.type == "missed_visit":
        if finding.context["is_dosing_visit"]:
            return (
                "Major",
                "A dosing visit was missed entirely; the subject went without a "
                "scheduled administration and no safety assessment was performed.",
                clause_ref,
            )
        return (
            "Minor",
            "A non-dosing visit was missed; limited impact on the primary "
            "endpoint but a gap in the safety monitoring record.",
            clause_ref,
        )

    if finding.type == "late_visit":
        extra_days = finding.context["extra_days"]
        retrieved_chunks = []
        # BUG-08: use a distinct local name to avoid shadowing the imported `severity` module
        if extra_days <= _LATE_VISIT_ADMIN_MAX_EXTRA_DAYS:
            sev = "Administrative"
        elif extra_days >= _LATE_VISIT_MINOR_MIN_EXTRA_DAYS:
            sev = "Minor"
        else:
            # The genuinely ambiguous band: retrieve real ICH E6(R2) grounding
            # (local, deterministic, never raises) and hand it to the one
            # optional live model call this detector makes.
            try:
                retrieved_chunks = retrieval.retrieve_ich_grounding(_LATE_VISIT_AMBIGUOUS_QUERY)
            except Exception:
                retrieved_chunks = []
            sev = llm_hook.classify_late_visit_severity(
                extra_days=extra_days,
                window_days=finding.context.get("window_days", 0),
                clause_text=clause_text,
                retrieved_chunks=retrieved_chunks,
            ) or "Minor"
        rationale = (
            "Visit occurred outside the allowed window; documentation lapse "
            "only, no discernible safety or data impact."
            if sev == "Administrative"
            else "Visit occurred outside the allowed window; no immediate "
            "safety impact but the deviation must be documented per Section 3.1."
        )
        if retrieved_chunks:
            rationale += " ICH grounding retrieved: " + ", ".join(c.citation for c in retrieved_chunks) + "."
        return sev, rationale, clause_ref

    if finding.type == "dosage_out_of_range":
        return (
            "Major",
            "Administered dose falls outside the protocol-defined safe range "
            "without documented PI approval, directly affecting subject safety "
            "and primary efficacy data.",
            clause_ref,
        )

    if finding.type == "banned_comedication":
        return (
            "Major",
            "Prohibited co-medication administered concurrently with Drug X; "
            "known CYP450 interaction poses a direct patient safety risk.",
            clause_ref,
        )

    if finding.type == "missing_procedure":
        procedure = finding.context["procedure"]
        # BUG-08: use `sev` to avoid shadowing the imported `severity` module
        sev = _MISSING_PROCEDURE_SEVERITY.get(procedure, _MISSING_PROCEDURE_DEFAULT_SEVERITY)
        if sev == "Major":
            rationale = (
                "Informed consent procedure is missing for the visit; a "
                "fundamental GCP/subject-rights requirement was not met."
            )
        elif sev == "Administrative":
            rationale = (
                "Routine vitals were not recorded at this visit; a "
                "documentation gap with no material safety or efficacy impact."
            )
        else:
            rationale = (
                f"The required '{procedure}' procedure was not completed at "
                "this visit, creating a gap in the safety/efficacy dataset."
            )
        return sev, rationale, clause_ref

    # BUG-01: handle the "other" generic deviation type
    if finding.type == "other":
        return (
            "Minor",
            "An unclassified deviation was recorded; review required.",
            clause_ref,
        )

    raise ValueError(f"Unknown finding type: {finding.type}")
