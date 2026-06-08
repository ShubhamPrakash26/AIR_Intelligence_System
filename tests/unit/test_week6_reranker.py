"""Unit tests for Week 6 — CrossEncoderReranker."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pytest

from src.retrieval.reranker import CrossEncoderReranker, RerankResult
from src.retrieval.similarity_search import SimilaritySearchResult


# ---------------------------------------------------------------------------
# Fake CrossEncoder
# ---------------------------------------------------------------------------


class _FakeCrossEncoder:
    """Fake CrossEncoder whose rank() returns scores based on document length.

    Longer documents score higher — predictable enough to write assertions
    against without downloading a 500 MB model.
    """

    def rank(
        self, query: str, documents: list[str], top_k: int | None = None
    ) -> list[dict[str, Any]]:
        scored = [
            {"corpus_id": i, "score": float(len(doc))}
            for i, doc in enumerate(documents)
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        if top_k is not None:
            scored = scored[:top_k]
        return scored

    def predict(self, pairs: list[list[str]]) -> np.ndarray:
        return np.array([float(len(pair[1])) for pair in pairs])


def _make_result(iid: str, score: float, **meta) -> SimilaritySearchResult:
    return SimilaritySearchResult(incident_id=iid, score=score, rank=1, metadata=meta)


# ---------------------------------------------------------------------------
# result_to_text
# ---------------------------------------------------------------------------


class TestResultToText:
    def test_all_fields_present(self):
        r = _make_result(
            "a",
            0.9,
            incident_type=["Airway", "Medication"],
            severity="High",
            surgery_type="Cardiac",
            root_cause="Communication failure",
            key_learning="Use checklists",
            source="AIR",
        )
        text = CrossEncoderReranker.result_to_text(r)
        assert "Airway" in text
        assert "Medication" in text
        assert "High" in text
        assert "Cardiac" in text
        assert "Communication failure" in text
        assert "Use checklists" in text
        assert "AIR" in text

    def test_no_metadata_returns_fallback(self):
        r = _make_result("b", 0.5)
        text = CrossEncoderReranker.result_to_text(r)
        assert text == "No metadata available."

    def test_partial_metadata(self):
        r = _make_result("c", 0.7, severity="Low", root_cause="Equipment failure")
        text = CrossEncoderReranker.result_to_text(r)
        assert "Low" in text
        assert "Equipment failure" in text

    def test_incident_type_string_not_list(self):
        r = _make_result("d", 0.6, incident_type="Airway")
        text = CrossEncoderReranker.result_to_text(r)
        assert "Airway" in text


# ---------------------------------------------------------------------------
# CrossEncoderReranker.rerank()
# ---------------------------------------------------------------------------


class TestRerank:
    def _reranker(self, threshold: float | None = None) -> CrossEncoderReranker:
        return CrossEncoderReranker(model=_FakeCrossEncoder(), threshold=threshold)

    def test_empty_input_returns_empty(self):
        r = self._reranker()
        assert r.rerank("query", []) == []

    def test_returns_rerank_results(self):
        results = [
            _make_result("a", 0.9, root_cause="Short"),
            _make_result("b", 0.5, root_cause="A much longer root cause explanation that has more text"),
        ]
        out = self._reranker().rerank("airway management", results)
        assert len(out) == 2
        assert all(isinstance(r, RerankResult) for r in out)

    def test_rerank_order_reflects_fake_scores(self):
        """Fake model scores by doc length, so longer doc gets rank 1."""
        short = _make_result("short", 0.9, root_cause="x")
        long = _make_result("long", 0.5, root_cause="this is a much longer root cause description with many words")
        out = self._reranker().rerank("q", [short, long])
        # long should be reranked to rank 1 (higher score from fake model)
        assert out[0].incident_id == "long"
        assert out[0].rerank_rank == 1

    def test_original_rank_preserved(self):
        r1 = SimilaritySearchResult(incident_id="a", score=0.9, rank=1, metadata={"root_cause": "x"})
        r2 = SimilaritySearchResult(incident_id="b", score=0.8, rank=2, metadata={"root_cause": "xx"})
        out = self._reranker().rerank("q", [r1, r2])
        original_ranks = {o.incident_id: o.original_rank for o in out}
        assert original_ranks["a"] == 1
        assert original_ranks["b"] == 2

    def test_similarity_score_preserved(self):
        r = _make_result("a", 0.77, root_cause="test")
        out = self._reranker().rerank("q", [r])
        assert out[0].similarity_score == pytest.approx(0.77)

    def test_threshold_filters_low_scores(self):
        """Fake scores = doc length; short doc has score < threshold → excluded."""
        short = _make_result("short", 0.9, root_cause="x")   # score = len("Root cause: x\n") ≈ small
        long = _make_result(
            "long",
            0.5,
            root_cause="z" * 200,   # very long → large score
        )
        out = self._reranker(threshold=100.0).rerank("q", [short, long])
        # Only the long result should survive the threshold
        ids = {r.incident_id for r in out}
        assert "long" in ids
        assert "short" not in ids

    def test_top_k_truncates(self):
        results = [_make_result(str(i), 0.5, root_cause="x" * i) for i in range(1, 6)]
        out = self._reranker().rerank("q", results, top_k=2)
        assert len(out) == 2

    def test_model_name_default(self):
        r = CrossEncoderReranker()
        assert r.model_name == "BAAI/bge-reranker-large"

    def test_model_name_custom(self):
        r = CrossEncoderReranker(model_name="custom/model")
        assert r.model_name == "custom/model"


# ---------------------------------------------------------------------------
# RerankResult
# ---------------------------------------------------------------------------


class TestRerankResult:
    def test_fields(self):
        r = RerankResult(
            incident_id="abc",
            original_rank=3,
            rerank_rank=1,
            similarity_score=0.7,
            rerank_score=0.95,
            metadata={"severity": "High"},
        )
        assert r.incident_id == "abc"
        assert r.original_rank == 3
        assert r.rerank_rank == 1
        assert r.similarity_score == pytest.approx(0.7)
        assert r.rerank_score == pytest.approx(0.95)
        assert r.metadata["severity"] == "High"
