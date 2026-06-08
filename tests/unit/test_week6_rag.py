"""Unit tests for Week 6 — RAGRetriever and RetrievedContext."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.retrieval.rag import RAGRetriever, RetrievedContext
from src.retrieval.reranker import CrossEncoderReranker, RerankResult
from src.retrieval.similarity_search import SimilaritySearchResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ssr(iid: str, score: float, **meta) -> SimilaritySearchResult:
    return SimilaritySearchResult(incident_id=iid, score=score, rank=1, metadata=meta)


def _make_rerank(iid: str, rerank_score: float, **meta) -> RerankResult:
    return RerankResult(
        incident_id=iid,
        original_rank=1,
        rerank_rank=1,
        similarity_score=0.5,
        rerank_score=rerank_score,
        metadata=meta,
    )


def _mock_search_engine(results: list[SimilaritySearchResult]) -> MagicMock:
    engine = MagicMock()
    engine.search_by_text.return_value = results
    engine.search_by_incident.return_value = results
    engine._embed = MagicMock()
    engine._embed.build_embed_text.return_value = "test embed text"
    return engine


def _mock_reranker(reranked: list[RerankResult]) -> MagicMock:
    r = MagicMock(spec=CrossEncoderReranker)
    r.rerank.return_value = reranked
    return r


# ---------------------------------------------------------------------------
# RetrievedContext
# ---------------------------------------------------------------------------


class TestRetrievedContext:
    def test_final_results_returns_similarity_when_not_reranked(self):
        ssr = [_make_ssr("a", 0.8)]
        ctx = RetrievedContext(query="q", results=ssr)
        assert ctx.final_results is ssr

    def test_final_results_returns_reranked_when_flagged(self):
        ssr = [_make_ssr("a", 0.8)]
        rr = [_make_rerank("a", 0.9)]
        ctx = RetrievedContext(query="q", results=ssr, reranked=rr, was_reranked=True)
        assert ctx.final_results is rr

    def test_top_result_none_when_empty(self):
        ctx = RetrievedContext(query="q", results=[])
        assert ctx.top_result is None

    def test_top_result_returns_first(self):
        r1 = _make_ssr("a", 0.9)
        r2 = _make_ssr("b", 0.5)
        ctx = RetrievedContext(query="q", results=[r1, r2])
        assert ctx.top_result is r1


# ---------------------------------------------------------------------------
# RAGRetriever.format_context
# ---------------------------------------------------------------------------


class TestFormatContext:
    def test_empty_results_message(self):
        text = RAGRetriever.format_context([])
        assert "No relevant" in text

    def test_includes_incident_ids(self):
        results = [_make_ssr("abc-123", 0.9, severity="High")]
        text = RAGRetriever.format_context(results)
        assert "abc-123" in text

    def test_includes_metadata_fields(self):
        results = [
            _make_ssr(
                "id1",
                0.85,
                incident_type=["Airway"],
                severity="Critical",
                surgery_type="Cardiac",
                root_cause="Communication",
                key_learning="Pre-op checklist",
            )
        ]
        text = RAGRetriever.format_context(results)
        assert "Airway" in text
        assert "Critical" in text
        assert "Communication" in text
        assert "Pre-op checklist" in text

    def test_includes_query_header(self):
        results = [_make_ssr("x", 0.7)]
        text = RAGRetriever.format_context(results, query="airway event")
        assert "Query: airway event" in text

    def test_max_results_truncates(self):
        results = [_make_ssr(str(i), 0.5) for i in range(5)]
        text = RAGRetriever.format_context(results, max_results=2)
        assert "Incident 2" in text
        assert "Incident 3" not in text

    def test_similarity_score_shown_for_ssr(self):
        results = [_make_ssr("a", 0.73)]
        text = RAGRetriever.format_context(results)
        assert "0.7300" in text

    def test_rerank_score_shown_for_rerank_result(self):
        results = [_make_rerank("a", 0.921)]
        text = RAGRetriever.format_context(results)
        assert "0.9210" in text
        assert "reranked" in text

    def test_count_line(self):
        results = [_make_ssr("a", 0.8), _make_ssr("b", 0.6)]
        text = RAGRetriever.format_context(results)
        assert "2 similar" in text


# ---------------------------------------------------------------------------
# RAGRetriever.retrieve
# ---------------------------------------------------------------------------


class TestRAGRetrieverRetrieve:
    def _retriever(
        self, results: list[SimilaritySearchResult], reranked: list[RerankResult] | None = None
    ) -> RAGRetriever:
        search_engine = _mock_search_engine(results)
        reranker = _mock_reranker(reranked or []) if reranked is not None else None
        return RAGRetriever(search_engine=search_engine, reranker=reranker)

    def test_basic_retrieve_returns_context(self):
        results = [_make_ssr("a", 0.9), _make_ssr("b", 0.7)]
        ret = self._retriever(results)
        ctx = ret.retrieve("airway management")
        assert isinstance(ctx, RetrievedContext)
        assert len(ctx.results) == 2
        assert not ctx.was_reranked

    def test_retrieve_calls_search_with_top_k(self):
        ret = self._retriever([])
        ret.retrieve("test query", top_k=10)
        ret._search.search_by_text.assert_called_once_with(
            "test query", top_k=10, filters=None
        )

    def test_retrieve_passes_filters(self):
        from src.retrieval.similarity_search import SearchFilters

        ret = self._retriever([])
        f = SearchFilters(severity="High")
        ret.retrieve("test", filters=f)
        _, kwargs = ret._search.search_by_text.call_args
        assert kwargs["filters"] is f

    def test_context_text_populated(self):
        results = [_make_ssr("a", 0.8, root_cause="Equipment")]
        ret = self._retriever(results)
        ctx = ret.retrieve("test")
        assert ctx.context_text != ""
        assert "Equipment" in ctx.context_text

    def test_reranking_applied_when_requested(self):
        results = [_make_ssr("a", 0.9)]
        reranked = [_make_rerank("a", 0.95)]
        ret = self._retriever(results, reranked=reranked)
        ctx = ret.retrieve("test", rerank=True)
        assert ctx.was_reranked
        assert len(ctx.reranked) == 1
        assert ctx.reranked[0].rerank_score == pytest.approx(0.95)

    def test_rerank_skipped_when_no_reranker(self):
        results = [_make_ssr("a", 0.9)]
        # No reranker provided
        search_engine = _mock_search_engine(results)
        ret = RAGRetriever(search_engine=search_engine, reranker=None)
        ctx = ret.retrieve("test", rerank=True)
        assert not ctx.was_reranked

    def test_empty_results_returns_no_incidents_text(self):
        ret = self._retriever([])
        ctx = ret.retrieve("nothing here")
        assert "No relevant" in ctx.context_text


# ---------------------------------------------------------------------------
# RAGRetriever.retrieve_for_incident
# ---------------------------------------------------------------------------


class TestRAGRetrieverRetrieveForIncident:
    def test_calls_search_by_incident(self):
        incident = MagicMock()
        incident.incident_id = "test-id"
        results = [_make_ssr("a", 0.8)]
        search_engine = _mock_search_engine(results)
        ret = RAGRetriever(search_engine=search_engine)
        ctx = ret.retrieve_for_incident(incident)
        search_engine.search_by_incident.assert_called_once()
        assert isinstance(ctx, RetrievedContext)

    def test_passes_analysis_to_search(self):
        incident = MagicMock()
        analysis = MagicMock()
        search_engine = _mock_search_engine([])
        ret = RAGRetriever(search_engine=search_engine)
        ret.retrieve_for_incident(incident, analysis=analysis)
        _, kwargs = search_engine.search_by_incident.call_args
        assert kwargs["analysis"] is analysis


# ---------------------------------------------------------------------------
# RAGRetriever.from_components factory
# ---------------------------------------------------------------------------


class TestRAGRetrieverFactory:
    def test_from_components_creates_retriever(self):
        embed = MagicMock()
        store = MagicMock()
        ret = RAGRetriever.from_components(embed, store)
        assert isinstance(ret, RAGRetriever)
        assert isinstance(ret._search, MagicMock.__class__) or ret._search is not None

    def test_from_components_with_reranker(self):
        embed = MagicMock()
        store = MagicMock()
        reranker = MagicMock()
        ret = RAGRetriever.from_components(embed, store, reranker=reranker)
        assert ret._reranker is reranker
