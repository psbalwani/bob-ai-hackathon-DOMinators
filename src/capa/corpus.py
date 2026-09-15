"""Evidence retrieval over the protocol's own clause text and Track C's
curated ICH E6(R2) corpus (src/data/ich_e6r2/guideline_chunks.json).

A Deviation object already carries a validated `protocol_clause_ref` (Track
A's severity.py resolves it against protocol["protocol_sections"], so it can
never be a hallucinated section) -- this module only adds the ICH-side
grounding, keyed off `(deviation.type, deviation.severity)`, the same pairing
severity.py itself uses to decide the missing_procedure sub-case. Every chunk
id returned here is checked against the loaded corpus, so a CAPA report's
`evidence_citations` can never cite an ICH section that isn't actually in
guideline_chunks.json.
"""

from __future__ import annotations

import json
from pathlib import Path

ICH_CORPUS_PATH = Path(__file__).resolve().parent.parent / "data" / "ich_e6r2" / "guideline_chunks.json"

# Every CAPA cites Section 5.20 (Noncompliance) -- it's the direct ICH basis
# for requiring a corrective/preventive action at all, not just a logged finding.
NONCOMPLIANCE_CHUNK_ID = "ICH-E6R2-5.20-NONCOMPLIANCE"

# type -> ICH chunk_id. missing_procedure branches on severity because that's
# how severity.py itself distinguishes informed_consent (Major) from other
# procedures (Minor/Administrative) -- there's no raw procedure name on a
# Deviation object to re-derive it from.
_ICH_CHUNK_FOR_TYPE = {
    "missed_visit": "ICH-E6R2-4.5-PROTOCOL-COMPLIANCE",
    "late_visit": "ICH-E6R2-4.5-PROTOCOL-COMPLIANCE",
    "dosage_out_of_range": "ICH-E6R2-4.6-INVESTIGATIONAL-PRODUCT",
    "banned_comedication": "ICH-E6R2-4.6-INVESTIGATIONAL-PRODUCT",
}
_MISSING_PROCEDURE_CHUNK_BY_SEVERITY = {
    "Major": "ICH-E6R2-4.8-INFORMED-CONSENT",
    "Minor": "ICH-E6R2-4.9-RECORDS-REPORTS",
    "Administrative": "ICH-E6R2-4.9-RECORDS-REPORTS",
}


def load_ich_corpus(path: Path = ICH_CORPUS_PATH) -> dict[str, dict]:
    chunks = json.loads(path.read_text(encoding="utf-8"))
    return {c["chunk_id"]: c for c in chunks}


def ich_chunks_for_deviation(corpus: dict[str, dict], dev_type: str, severity: str) -> list[dict]:
    """Real, corpus-verified ICH chunks grounding this deviation type/severity."""
    if dev_type == "missing_procedure":
        chunk_id = _MISSING_PROCEDURE_CHUNK_BY_SEVERITY.get(severity, "ICH-E6R2-4.9-RECORDS-REPORTS")
    else:
        chunk_id = _ICH_CHUNK_FOR_TYPE.get(dev_type)

    chunk_ids = [chunk_id] if chunk_id else []
    chunk_ids.append(NONCOMPLIANCE_CHUNK_ID)
    chunk_ids.append(f"ICH-TAXONOMY-{severity.upper()}")

    # Every id above is a literal from our own corpus map, but resolve
    # defensively against the loaded corpus anyway -- if a chunk_id ever
    # doesn't exist, drop it rather than citing something unverifiable.
    seen: set[str] = set()
    chunks = []
    for cid in chunk_ids:
        if cid in corpus and cid not in seen:
            seen.add(cid)
            chunks.append(corpus[cid])
    return chunks


def ich_citation_string(chunk: dict) -> str:
    if chunk["ich_section"]:
        return f"ICH E6(R2) Section {chunk['ich_section']} - {chunk['title']}"
    return f"Internal taxonomy note - {chunk['title']}"
