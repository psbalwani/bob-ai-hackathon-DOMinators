"""Unit tests for src/detection/retrieval.py -- the local TF-IDF retrieval
layer over Track C's ICH E6(R2) guideline corpus.

Requires src/data/ich_e6r2/guideline_chunks.json to exist (Track C's
deliverable, already committed).
"""

import pytest

from src.detection.retrieval import TfidfIndex, load_guideline_chunks, retrieve_ich_grounding

ALL_CHUNK_IDS = {c.chunk_id for c in load_guideline_chunks()}


def test_corpus_loads_all_eleven_chunks():
    chunks = load_guideline_chunks()
    assert len(chunks) == 11
    assert {c.source_type for c in chunks} == {"ich_paraphrase", "internal_taxonomy"}


def test_late_visit_ambiguous_query_retrieves_taxonomy_chunks():
    """This is the exact query severity.py uses for the ambiguous late-visit
    boundary -- both taxonomy chunks explicitly discuss this exact case."""
    query = (
        "late visit outside protocol window severity minor or administrative "
        "documentation lapse"
    )
    results = retrieve_ich_grounding(query, top_k=2)
    result_ids = {c.chunk_id for c in results}
    assert result_ids == {"ICH-TAXONOMY-MINOR", "ICH-TAXONOMY-ADMINISTRATIVE"}


def test_informed_consent_query_retrieves_relevant_chunk():
    results = retrieve_ich_grounding("missing informed consent at baseline visit", top_k=3)
    result_ids = {c.chunk_id for c in results}
    assert "ICH-E6R2-4.8-INFORMED-CONSENT" in result_ids


def test_dosage_query_retrieves_investigational_product_chunk():
    results = retrieve_ich_grounding("dose administered outside protocol range", top_k=3)
    result_ids = {c.chunk_id for c in results}
    assert "ICH-E6R2-4.6-INVESTIGATIONAL-PRODUCT" in result_ids


def test_no_hallucinated_citations():
    """Every retrieved chunk must be a real entry from the loaded corpus."""
    for query in [
        "late visit severity",
        "banned co-medication safety",
        "missing procedure vitals",
        "risk scoring quality management",
    ]:
        for chunk in retrieve_ich_grounding(query, top_k=5):
            assert chunk.chunk_id in ALL_CHUNK_IDS


def test_top_k_is_respected():
    results = retrieve_ich_grounding("protocol compliance deviation", top_k=1)
    assert len(results) <= 1


def test_irrelevant_query_returns_no_false_matches():
    """A query sharing no vocabulary with the corpus should retrieve nothing,
    not an arbitrary top-k padded with unrelated chunks."""
    results = retrieve_ich_grounding("xylophone quokka birthday cake zzzqqq")
    assert results == []


def test_missing_corpus_degrades_gracefully(monkeypatch):
    """retrieve_ich_grounding must never raise, even if the corpus can't be
    loaded (e.g. a broken/missing file in some other environment)."""
    from src.detection import retrieval as retrieval_module

    def _boom():
        raise FileNotFoundError("corpus missing")

    monkeypatch.setattr(retrieval_module, "load_guideline_chunks", _boom)
    assert retrieve_ich_grounding("anything") == []


class TestTfidfIndexDirectly:
    def test_search_orders_by_relevance(self):
        index = TfidfIndex(load_guideline_chunks())
        results = index.search("informed consent subject rights", top_k=3)
        assert results, "expected at least one match"
        top_chunk, top_score = results[0]
        assert top_chunk.chunk_id in {"ICH-E6R2-4.8-INFORMED-CONSENT", "ICH-TAXONOMY-MAJOR"}
        # scores should be sorted descending
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)
