"""Optional watsonx.ai-assisted classification for genuinely ambiguous cases.

Only one case in this detector is ambiguous by rule alone: a late visit whose
extra lateness sits in the boundary band (see severity.py). Everything else
is fully deterministic and never reaches this module.

If WATSONX_API_KEY isn't set, or the SDK isn't installed, or the call fails
for any reason, `classify_late_visit_severity` returns None and the caller
falls back to its own deterministic default -- this module must never raise.
"""

from __future__ import annotations

import os


def classify_late_visit_severity(*, extra_days: int, window_days: int, clause_text: str) -> str | None:
    """Return "Minor" or "Administrative", or None to fall back to the rule default."""
    if not os.environ.get("WATSONX_API_KEY"):
        return None

    try:
        from ibm_watsonx_ai.foundation_models import ModelInference  # type: ignore
    except ImportError:
        return None

    prompt = (
        "A clinical trial visit occurred {extra_days} day(s) outside its "
        "{window_days}-day allowed window. Per this protocol clause:\n"
        "{clause_text}\n\n"
        "Classify this deviation's severity as exactly one word: "
        "Minor or Administrative."
    ).format(extra_days=extra_days, window_days=window_days, clause_text=clause_text)

    try:
        model = ModelInference(
            model_id="ibm/granite-13b-instruct-v2",
            project_id=os.environ.get("WATSONX_PROJECT_ID"),
            credentials={
                "url": os.environ.get("WATSONX_URL", "https://us-south.ml.cloud.ibm.com"),
                "apikey": os.environ["WATSONX_API_KEY"],
            },
        )
        response = model.generate_text(prompt=prompt).strip()
    except Exception:
        return None

    if "minor" in response.lower():
        return "Minor"
    if "administrative" in response.lower():
        return "Administrative"
    return None
