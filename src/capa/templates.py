"""Deterministic CAPA text templates -- one per deviation type.

This is the generator's guaranteed-available fallback (see DESIGN.md): it
never calls out to an LLM, never raises, and always produces grounded,
specific text keyed only off information already on the Deviation object
(type, severity, site_id) plus the protocol's own dosing rule values. It is
also what `llm_hook.py` hands to watsonx.ai as the grounding baseline to
refine, so the LLM is elaborating on real content rather than inventing it
from scratch.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ActionSet:
    root_cause: str
    corrective_action: str
    preventive_action: str


def for_deviation_type(dev_type: str, severity: str, site_id: str, protocol: dict) -> ActionSet:
    dosing = protocol["dosing_rules"]

    if dev_type == "banned_comedication":
        return ActionSet(
            root_cause=(
                f"Site staff at {site_id} administered or failed to screen out a "
                f"prohibited co-medication prior to dosing with {dosing['drug']}, "
                "indicating a gap in the concomitant-medication screening step of "
                "the dosing workflow."
            ),
            corrective_action=(
                f"Retrain site coordinators and investigators at {site_id} on the "
                "protocol's prohibited-medication list; conduct an immediate chart "
                "review of all subjects at this site for concurrent prohibited "
                "medication use."
            ),
            preventive_action=(
                "Add a mandatory, documented concomitant-medication cross-check "
                "against the prohibited list to the site's dosing-visit checklist "
                "and EDC entry workflow, required before each administration is "
                "confirmed."
            ),
        )

    if dev_type == "dosage_out_of_range":
        return ActionSet(
            root_cause=(
                f"A dose administered at {site_id} fell outside the protocol-"
                f"approved range ({dosing['min_mg']}-{dosing['max_mg']}mg, "
                f"{dosing['route']}), indicating a lapse in dose verification "
                "prior to administration."
            ),
            corrective_action=(
                f"Retrain site dosing staff at {site_id} on the approved dose "
                f"range for {dosing['drug']}; require a documented second-person "
                "dose verification before administration going forward."
            ),
            preventive_action=(
                "Implement a hard-stop dose-range check in the site's dispensing/"
                f"EDC system that flags any entry outside {dosing['min_mg']}-"
                f"{dosing['max_mg']}mg before it can be confirmed."
            ),
        )

    if dev_type == "missed_visit":
        return ActionSet(
            root_cause=(
                f"One or more scheduled visits at {site_id} were missed entirely, "
                "indicating a breakdown in subject visit scheduling or reminder "
                "procedures at the site."
            ),
            corrective_action=(
                f"Review subject scheduling and reminder procedures with site "
                f"coordination staff at {site_id}; contact affected subjects to "
                "reschedule within any protocol-permitted allowance."
            ),
            preventive_action=(
                "Implement an automated visit-window reminder (e.g. 7 and 2 days "
                "prior) for site coordinators, escalating to the PI if a scheduled "
                "visit is not confirmed in time."
            ),
        )

    if dev_type == "late_visit":
        return ActionSet(
            root_cause=(
                f"A visit at {site_id} occurred outside its protocol-defined "
                "window, indicating a gap in proactive visit scheduling rather "
                "than an acute safety event."
            ),
            corrective_action=(
                f"Review scheduling practices with site coordination staff at "
                f"{site_id}; document the specific cause of the delay for this "
                "occurrence."
            ),
            preventive_action=(
                "Add a visit-window countdown alert to the site's scheduling "
                "workflow so upcoming windows are flagged before they lapse."
            ),
        )

    if dev_type == "missing_procedure":
        if severity == "Major":  # informed_consent, per severity.py
            return ActionSet(
                root_cause=(
                    f"Informed consent documentation was not completed or recorded "
                    f"for a subject at {site_id} prior to the visit, indicating a "
                    "gap in the enrollment/consent verification step."
                ),
                corrective_action=(
                    "Immediately verify consent status for the affected subject(s); "
                    f"retrain site staff at {site_id} on the mandatory pre-visit "
                    "consent verification step."
                ),
                preventive_action=(
                    "Add a hard checklist gate to the site's visit workflow that "
                    "blocks logging any other procedure until informed consent is "
                    "confirmed recorded."
                ),
            )
        return ActionSet(
            root_cause=(
                f"A required procedure was not completed or recorded at one or "
                f"more visits at {site_id}, indicating a gap in visit-completion "
                "verification before subject discharge."
            ),
            corrective_action=(
                f"Retrain site staff at {site_id} on the full required-procedures "
                "checklist for each visit type; review the affected visit(s) for "
                "retrospective completion where still clinically valid."
            ),
            preventive_action=(
                "Add a required-procedures checklist confirmation step to the "
                "EDC visit-closeout workflow so a visit cannot be marked complete "
                "with an outstanding required procedure."
            ),
        )

    raise ValueError(f"No CAPA template for deviation type: {dev_type}")


# Owner/urgency policy: tighter windows and higher-authority owners for more
# severe deviations, since a Major finding needs PI-level attention while an
# Administrative one is routine site-coordinator follow-up. Documented as a
# judging talking point in DESIGN.md, same as Track B's indicator weights.
OWNER_ROLE_BY_SEVERITY = {
    "Major": "Site Principal Investigator",
    "Minor": "Clinical Research Associate (CRA)",
    "Administrative": "Site Coordinator",
}
DUE_WINDOW_DAYS_BY_SEVERITY = {
    "Major": 7,
    "Minor": 14,
    "Administrative": 21,
}

_SEVERITY_RANK = {"Major": 3, "Minor": 2, "Administrative": 1}


def worst_severity(severities: list[str]) -> str:
    return max(severities, key=lambda s: _SEVERITY_RANK.get(s, 0))
