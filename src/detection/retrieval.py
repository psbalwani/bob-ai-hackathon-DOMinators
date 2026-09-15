"""Lightweight local retrieval ("vector store") over the ICH E6(R2) guideline
corpus (Track C, `src/data/ich_e6r2/guideline_chunks.json`) plus the
protocol's own clause text, used to ground Track A's one genuinely ambiguous
classification case -- see severity.py's late-visit boundary band.

Pure-Python TF-IDF + cosine similarity: no external ML dependency, no
network call, deterministic and exactly unit-testable. Appropriate at this
corpus's scale (~15 short documents) -- a real vector DB (Chroma/FAISS)
would be pure overhead here, and this keeps retrieval quality independent of
whatever watsonx.ai credentials/quota a given environment has (unlike the
one LLM call this module feeds into, which does depend on that).
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# BUG-05: use __file__-relative path so the module works regardless of cwd
# (e.g. inside Docker or when tests are run from a subdirectory).
GUIDELINE_CHUNKS_PATH = Path(__file__).resolve().parent.parent / "data" / "ich_e6r2" / "guideline_chunks.json"

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Chunk:
    chunk_id: str
    source_type: str
    title: str
    text: str
    official_source_url: str | None = None

    @property
    def citation(self) -> str:
        return f"{self.chunk_id} - {self.title}"


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


# BUG-07: lru_cache on a function with a default arg produces two distinct cache
# keys — one for calls with no argument (uses the default sentinel) and one for
# calls that pass GUIDELINE_CHUNKS_PATH explicitly — so the file is re-read every
# time the call pattern alternates.  Remove the parameter entirely: the module-level
# constant is always the right path and callers that need a different path can call
# json.loads() directly.
@lru_cache(maxsize=1)
def load_guideline_chunks() -> tuple[Chunk, ...]:
    path = GUIDELINE_CHUNKS_PATH
    raw = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        Chunk(
            chunk_id=c["chunk_id"],
            source_type=c["source_type"],
            title=c["title"],
            text=c["text"],
            official_source_url=c.get("official_source_url"),
        )
        for c in raw
    )


def protocol_clause_chunks(protocol: dict) -> list[Chunk]:
    """The protocol's own protocol_sections, in the same Chunk shape, so a
    single index can retrieve across both corpora at once."""
    return [
        Chunk(
            chunk_id=f"PROTOCOL-{s['section_id']}",
            source_type="protocol_clause",
            title=s["title"],
            text=s["text"],
        )
        for s in protocol.get("protocol_sections", [])
    ]


class TfidfIndex:
    """A minimal TF-IDF + cosine-similarity index over a fixed corpus."""

    def __init__(self, chunks: list[Chunk] | tuple[Chunk, ...]):
        self._chunks = list(chunks)
        doc_tokens = [_tokenize(c.title + " " + c.text) for c in self._chunks]

        doc_freq: dict[str, int] = {}
        for tokens in doc_tokens:
            for term in set(tokens):
                doc_freq[term] = doc_freq.get(term, 0) + 1

        n_docs = len(self._chunks)
        # Smoothed idf (sklearn-style): terms in every doc still get weight > 0.
        self._idf = {term: math.log((n_docs + 1) / (freq + 1)) + 1.0 for term, freq in doc_freq.items()}
        self._doc_vectors = [self._vectorize(tokens) for tokens in doc_tokens]

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        counts: dict[str, int] = {}
        for t in tokens:
            counts[t] = counts.get(t, 0) + 1
        vec = {t: (count / len(tokens)) * self._idf.get(t, 0.0) for t, count in counts.items()}
        norm = math.sqrt(sum(w * w for w in vec.values())) or 1.0
        return {t: w / norm for t, w in vec.items()}

    @staticmethod
    def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if not a or not b:
            return 0.0
        shared = set(a) & set(b)
        return sum(a[t] * b[t] for t in shared)

    def search(self, query: str, top_k: int = 3) -> list[tuple[Chunk, float]]:
        query_vec = self._vectorize(_tokenize(query))
        scored = [
            (chunk, self._cosine(query_vec, doc_vec))
            for chunk, doc_vec in zip(self._chunks, self._doc_vectors)
        ]
        scored = [pair for pair in scored if pair[1] > 0]
        scored.sort(key=lambda pair: pair[1], reverse=True)
        return scored[:top_k]


def retrieve_ich_grounding(query: str, top_k: int = 2) -> list[Chunk]:
    """Retrieve the top_k most relevant ICH E6(R2) guideline chunks for a
    query. Returns [] (never raises) if the corpus can't be loaded, so a
    missing/broken corpus degrades gracefully rather than blocking
    classification."""
    try:
        chunks = load_guideline_chunks()  # always uses GUIDELINE_CHUNKS_PATH (BUG-07 fix)
    except (OSError, json.JSONDecodeError, KeyError):
        return []
    index = TfidfIndex(chunks)
    return [chunk for chunk, _score in index.search(query, top_k=top_k)]
