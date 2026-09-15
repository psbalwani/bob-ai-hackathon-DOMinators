# ICH E6(R2) GCP Guideline Corpus (Track C)

`guideline_chunks.json` is the chunked reference corpus for the RAG /
vector-store layer that grounds Track A's severity classifier and Track C's
CAPA generator, per `docs/03_team_division.md` (Track C, task 2) and
`docs/architecture.md` ("Vector Store: Chroma or FAISS ... chunked protocol
text + ICH E6(R2) GCP guideline text").

## What this is (and isn't)

- **8 `ich_paraphrase` chunks**: section-level **paraphrased summaries** of
  the ICH E6(R2) sections most relevant to this system's deviation types
  (protocol compliance, investigational product/dosing, informed consent,
  records, quality management, monitoring, noncompliance). Each chunk cites
  its real section number/title and links the official EMA-published PDF.
- **3 `internal_taxonomy` chunks**: our own Major/Minor/Administrative
  mapping, explicitly labeled as an internal classification convention, not
  ICH text.
- **This is not a verbatim reproduction of the ICH E6(R2) document.** The
  guideline is a copyrighted regulatory text; verbatim extraction wasn't
  feasible from the available source (the PDF didn't extract cleanly via
  available tooling) and wouldn't be appropriate to redistribute wholesale
  regardless. Each chunk is a good-faith paraphrase grounded in well-known,
  widely-taught GCP training material, written to preserve the section's
  actual regulatory substance and correct section numbering -- but it is
  **not a substitute for the primary source** in a real regulatory context.

## Known limitation (be upfront about this with judges if asked)

Section numbers and subsection counts (e.g. "4.5 has subsections
4.5.1-4.5.4") were corroborated via web search against the official ICH/EMA
document description. The prose summaries were written from general GCP
domain knowledge, not by reading the verbatim source text end-to-end line by
line. Before any real (non-hackathon) use, swap this corpus for the actual
ICH E6(R2) text (official source: EMA, linked in each chunk's
`official_source_url`) or have a GCP-trained reviewer verify each chunk
against it.

## Why the taxonomy note matters

`docs/01_project_planning.md` (FR4) requires severity classification to map
"explicitly to ICH E6(R2) GCP definitions." Worth being precise about this:
**ICH E6(R2) itself does not define a Major/Minor/Administrative severity
scale** -- that three-tier taxonomy is a common industry convention (seen
across many sponsor/CRO deviation SOPs), not a defined term in the ICH text.
The `ICH-TAXONOMY-*` chunks make that distinction explicit and ground each
tier in the closest real ICH principles/sections (2.3, 2.10, 4.5, 4.6, 4.8,
4.9, 5.20) rather than implying the three labels themselves are quoted from
ICH. This is the more defensible and more honest framing for a compliance
domain -- overclaiming "ICH defines Major deviations as..." would not hold
up under scrutiny from anyone who actually knows the document.

## Chunk shape

```json
{
  "chunk_id": "ICH-E6R2-5.20-NONCOMPLIANCE",
  "source_type": "ich_paraphrase",
  "ich_section": "5.20",
  "title": "Noncompliance",
  "text": "...",
  "official_source_url": "https://www.ema.europa.eu/en/documents/scientific-guideline/ich-guideline-good-clinical-practice-e6r2-step-5-revision-2_en.pdf"
}
```

`internal_taxonomy` chunks use the same shape with `ich_section: null` and
`official_source_url: null`, so a vector store loader can filter to
ICH-sourced-only chunks if it needs to distinguish primary source from our
own classification notes.

## How this plugs in

- Track A's RAG layer (`docs/architecture.md`) embeds and indexes these
  chunks alongside `protocol.json`'s `protocol_sections` (see
  `src/data/README.md`) so the severity classifier can retrieve and cite
  both the specific protocol clause *and* the ICH grounding for a
  deviation, matching the `severity_rationale` example in
  `docs/04_data_schema.md`: *"...per ICH E6(R2) Section 4.5."*
- Track C's CAPA generator should always retrieve `ICH-E6R2-5.20-NONCOMPLIANCE`
  (or the matching `ICH-TAXONOMY-*` chunk) alongside the deviation-specific
  chunk, since Section 5.20 is the direct textual basis for requiring a
  corrective/preventive action in the first place.
