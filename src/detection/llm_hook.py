"""Optional watsonx.ai-assisted classification for genuinely ambiguous cases.

Only one case in this detector is ambiguous by rule alone: a late visit whose
extra lateness sits in the boundary band (see severity.py). Everything else
is fully deterministic and never reaches this module.

If WATSONX_API_KEY isn't set, or the SDK isn't installed, or the call fails
for any reason, `classify_late_visit_severity` returns None and the caller
falls back to its own deterministic default -- this module must never raise.

Env vars (see src/.env.example):
    WATSONX_API_KEY    (required)
    WATSONX_URL        (required, e.g. https://eu-de.ml.cloud.ibm.com)
    WATSONX_SPACE_ID   (preferred -- a deployment space with a WML instance
                        attached) or WATSONX_PROJECT_ID (fallback; some
                        projects aren't associated with a WML instance and
                        will 403 -- see README for how to tell)
    WATSONX_MODEL_ID   (default: ibm/granite-13b-instruct-v2)
"""

from __future__ import annotations

import os

_SYSTEM_PROMPT = (
    "You are a clinical trial compliance classifier. You must respond with "
    "exactly one word: Minor or Administrative. No other text."
)


def classify_late_visit_severity(*, extra_days: int, window_days: int, clause_text: str) -> str | None:
    """Return "Minor" or "Administrative", or None to fall back to the rule default."""
    api_key = os.environ.get("WATSONX_API_KEY")
    url = os.environ.get("WATSONX_URL")
    space_id = os.environ.get("WATSONX_SPACE_ID")
    project_id = os.environ.get("WATSONX_PROJECT_ID")
    if not api_key or not url or not (space_id or project_id):
        return None

    try:
        from ibm_watsonx_ai.foundation_models import ModelInference  # type: ignore
    except ImportError:
        return None

    user_prompt = (
        f"{clause_text}\n\n"
        f"A clinical trial visit occurred {extra_days} extra day(s) beyond its "
        f"{window_days}-day allowed window. Classify this deviation's severity."
    )

    try:
        model = ModelInference(
            model_id=os.environ.get("WATSONX_MODEL_ID", "ibm/granite-13b-instruct-v2"),
            space_id=space_id,
            project_id=None if space_id else project_id,
            credentials={"url": url, "apikey": api_key},
        )
        response = model.chat(
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            params={"max_tokens": 10, "temperature": 0},
        )
        text = response["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

    if "minor" in text.lower():
        return "Minor"
    if "administrative" in text.lower():
        return "Administrative"
    return None
