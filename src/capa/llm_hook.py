"""Optional watsonx.ai-assisted drafting for CAPA narrative text.

Mirrors src/detection/llm_hook.py's resilience contract: if WATSONX_API_KEY
isn't set, the SDK isn't installed, or the call fails or returns something
unparseable for ANY reason, `draft_capa_text` returns None and the caller
(generator.py) falls back to templates.py's deterministic text unchanged.
This module must never raise.

Deliberately scoped: the LLM only ever refines the *prose* of an
already-generated root_cause/corrective_action/preventive_action baseline
(from templates.py, itself grounded in the real protocol + ICH clause text)
into a more specific, natural narrative. It is never asked to invent, and
its output is never used to populate, `evidence_citations` -- that field is
always built structurally by corpus.py from real Deviation/clause data,
regardless of whether this hook runs at all. That split is what keeps a CAPA
report's citations non-hallucinatable even when the LLM path is active.

Env vars: same four as src/detection/llm_hook.py (see src/.env.example).
"""

from __future__ import annotations

import json
import os

_SYSTEM_PROMPT = (
    "You are a clinical trial quality/compliance writer drafting a CAPA "
    "(Corrective and Preventive Action) report section. You will be given a "
    "baseline root cause, corrective action, and preventive action, already "
    "grounded in the trial's protocol and ICH E6(R2) GCP guideline. Rewrite "
    "them to be more specific and natural, using ONLY the facts given to "
    "you -- do not invent new protocol section numbers, dates, drug names, "
    "or facts not present in the input. Respond with ONLY a JSON object with "
    'exactly these keys: "root_cause", "corrective_action", '
    '"preventive_action". No other text, no markdown fences.'
)


def draft_capa_text(
    *,
    site_id: str,
    deviation_type: str,
    severity: str,
    deviation_count: int,
    clause_texts: list[str],
    baseline_root_cause: str,
    baseline_corrective_action: str,
    baseline_preventive_action: str,
) -> dict | None:
    """Return {"root_cause", "corrective_action", "preventive_action"}, or None."""
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

    grounding = "\n\n".join(clause_texts)
    user_prompt = (
        f"Site: {site_id}\n"
        f"Deviation type: {deviation_type}\n"
        f"Severity: {severity}\n"
        f"Number of related deviations in this report: {deviation_count}\n\n"
        f"Grounding clause text:\n{grounding}\n\n"
        f"Baseline root cause: {baseline_root_cause}\n"
        f"Baseline corrective action: {baseline_corrective_action}\n"
        f"Baseline preventive action: {baseline_preventive_action}"
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
            params={"max_tokens": 500, "temperature": 0.2},
        )
        text = response["choices"][0]["message"]["content"].strip()
        parsed = json.loads(text)
    except Exception:
        return None

    required_keys = {"root_cause", "corrective_action", "preventive_action"}
    if not isinstance(parsed, dict) or not required_keys.issubset(parsed.keys()):
        return None
    if not all(isinstance(parsed[k], str) and parsed[k].strip() for k in required_keys):
        return None

    return {k: parsed[k].strip() for k in required_keys}
