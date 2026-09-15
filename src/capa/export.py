"""Export a CapaReport for GET /capa/{capa_id}/export?format=pdf|markdown."""

from __future__ import annotations

from .models import CapaReport


def to_markdown(report: CapaReport) -> str:
    citations = "\n".join(f"- {c}" for c in report.evidence_citations)
    return f"""# CAPA Report {report.capa_id}

**Scope:** {report.scope}
**Site:** {report.site_id}
**Related deviations:** {", ".join(report.related_deviation_ids)}
**Generated:** {report.generated_at}

## Root Cause

{report.root_cause}

## Corrective Action

{report.corrective_action}

## Preventive Action

{report.preventive_action}

## Ownership

- **Suggested owner:** {report.suggested_owner_role}
- **Suggested due window:** {report.suggested_due_window_days} days

## Evidence Citations

{citations}
"""


def to_pdf_bytes(report: CapaReport) -> bytes | None:
    """Returns PDF bytes, or None if the optional `fpdf2` dependency isn't installed.

    Markdown export always works and is the reliable path for the demo;
    this is a nice-to-have on top of it, following the same
    "optional dependency, graceful fallback" pattern as llm_hook.py.
    """
    try:
        from fpdf import FPDF  # type: ignore
    except ImportError:
        return None

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.multi_cell(0, 10, f"CAPA Report {report.capa_id}")
    pdf.set_font("Helvetica", size=10)
    pdf.multi_cell(
        0, 6,
        f"Scope: {report.scope}   Site: {report.site_id}   Generated: {report.generated_at}",
    )
    pdf.ln(4)

    sections = [
        ("Root Cause", report.root_cause),
        ("Corrective Action", report.corrective_action),
        ("Preventive Action", report.preventive_action),
        (
            "Ownership",
            f"Suggested owner: {report.suggested_owner_role}\n"
            f"Suggested due window: {report.suggested_due_window_days} days",
        ),
        ("Evidence Citations", "\n".join(f"- {c}" for c in report.evidence_citations)),
    ]
    for title, body in sections:
        pdf.set_font("Helvetica", "B", 12)
        pdf.multi_cell(0, 8, title)
        pdf.set_font("Helvetica", size=10)
        pdf.multi_cell(0, 6, body)
        pdf.ln(2)

    return bytes(pdf.output())
