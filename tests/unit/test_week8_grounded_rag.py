"""Unit tests for Week 8 GroundedRAGPipeline and GroundedRetrievalResult.

Uses fake embedding / Qdrant infrastructure inherited from Week 6 test
patterns so no model downloads or external servers are needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.retrieval.evidence import EvidenceBundle, EvidenceTracker
from src.retrieval.query_preprocessor import QueryIntent, QueryPreprocessor
from src.retrieval.rag import (
    GroundedRAGPipeline,
    GroundedRetrievalResult,
    RAGRetriever,
    RetrievedContext,
)
from src.retrieval.similarity_search import SearchFilters, SimilaritySearchResult


# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------


def _make_search_result(
    incident_id: str,
    score: float,
    severity: str = "High",
) -> SimilaritySearchResult:
    return SimilaritySearchResult(
        incident_id=incident_id,
        score=score,
        rank=1,
        metadata={
            "severity": severity,
            "incident_type": ["Medication Error"],
            "root_cause": "labeling failure",
            "surgery_type": "Cardiac",
            "key_learning": "Double-check labeling",
        },
    )


def _make_mock_retriever(results: list[SimilaritySearchResult]) -> RAGRetriever:
    """Build a RAGRetriever whose retrieve() returns a pre-built RetrievedContext."""
    mock = MagicMock(spec=RAGRetriever)
    ctx = RetrievedContext(
        query="mock query",
        results=results,
        reranked=[],
        was_reranked=False,
        context_text="mock context",
    )
    mock.retrieve.return_value = ctx
    return mock


# ---------------------------------------------------------------------------
# GroundedRetrievalResult properties
# ---------------------------------------------------------------------------


class TestGroundedRetrievalResult:
    def _make_result(
        self,
        results: list[SimilaritySearchResult],
        reranked: list | None = None,
        was_reranked: bool = False,
    ) -> GroundedRetrievalResult:
        pq = QueryPreprocessor().preprocess("test query")
        bundle = EvidenceTracker().build_bundle("test query", results)
        return GroundedRetrievalResult(
            query="test query",
            processed_query=pq,
            results=results,
            reranked=reranked or [],
            was_reranked=was_reranked,
            context_text="ctx",
            evidence_bundle=bundle,
            grounded_context="grounded",
        )

    def test_final_results_returns_similarity_when_no_rerank(self) -> None:
        r = _make_search_result("id1", 0.9)
        result = self._make_result([r])
        assert result.final_results == [r]

    def test_final_results_returns_reranked_when_applicable(self) -> None:
        r = _make_search_result("id1", 0.9)
        rr = MagicMock()
        result = self._make_result([r], reranked=[rr], was_reranked=True)
        assert result.final_results == [rr]

    def test_top_result_when_empty(self) -> None:
        result = self._make_result([])
        assert result.top_result is None

    def test_top_result_returns_first(self) -> None:
        r1 = _make_search_result("id1", 0.9)
        r2 = _make_search_result("id2", 0.7)
        result = self._make_result([r1, r2])
        assert result.top_result == r1

    def test_grounded_context_stored(self) -> None:
        result = self._make_result([])
        assert result.grounded_context == "grounded"

    def test_evidence_bundle_accessible(self) -> None:
        r = _make_search_result("id1", 0.85)
        result = self._make_result([r])
        assert isinstance(result.evidence_bundle, EvidenceBundle)


# ---------------------------------------------------------------------------
# GroundedRAGPipeline initialisation
# ---------------------------------------------------------------------------


class TestGroundedRAGPipelineInit:
    def test_defaults_created_when_none(self) -> None:
        retriever = _make_mock_retriever([])
        pipeline = GroundedRAGPipeline(retriever)
        assert pipeline._preprocessor is not None
        assert pipeline._tracker is not None

    def test_injected_preprocessor_used(self) -> None:
        retriever = _make_mock_retriever([])
        custom_pp = QueryPreprocessor(severity_map={"catastrophic": "Critical"})
        pipeline = GroundedRAGPipeline(retriever, preprocessor=custom_pp)
        assert pipeline._preprocessor is custom_pp

    def test_injected_tracker_used(self) -> None:
        retriever = _make_mock_retriever([])
        custom_tracker = EvidenceTracker(high_threshold=0.95)
        pipeline = GroundedRAGPipeline(retriever, tracker=custom_tracker)
        assert pipeline._tracker is custom_tracker


# ---------------------------------------------------------------------------
# GroundedRAGPipeline.retrieve
# ---------------------------------------------------------------------------


class TestGroundedRAGPipelineRetrieve:
    def test_basic_retrieve_returns_grounded_result(self) -> None:
        r = _make_search_result("id1", 0.85)
        retriever = _make_mock_retriever([r])
        pipeline = GroundedRAGPipeline(retriever)
        result = pipeline.retrieve("medication errors in cardiac surgery")
        assert isinstance(result, GroundedRetrievalResult)

    def test_intent_detected_in_result(self) -> None:
        retriever = _make_mock_retriever([])
        pipeline = GroundedRAGPipeline(retriever)
        result = pipeline.retrieve("why do medication errors occur?")
        assert result.processed_query.intent == QueryIntent.ROOT_CAUSE

    def test_evidence_bundle_present(self) -> None:
        r = _make_search_result("id1", 0.85)
        retriever = _make_mock_retriever([r])
        pipeline = GroundedRAGPipeline(retriever)
        result = pipeline.retrieve("cardiac errors")
        assert result.evidence_bundle is not None
        assert result.evidence_bundle.total_retrieved == 1

    def test_grounded_context_non_empty_when_results(self) -> None:
        r = _make_search_result("id1", 0.85)
        retriever = _make_mock_retriever([r])
        pipeline = GroundedRAGPipeline(retriever)
        result = pipeline.retrieve("medication errors")
        assert len(result.grounded_context) > 0

    def test_preprocessing_bypass_skips_filter_inference(self) -> None:
        retriever = _make_mock_retriever([])
        pipeline = GroundedRAGPipeline(retriever)
        result = pipeline.retrieve("critical incidents", use_preprocessing=False)
        # With preprocessing disabled, no filters should be inferred
        retriever.retrieve.assert_called_once()
        call_kwargs = retriever.retrieve.call_args
        # filters arg should be None (no preprocessing inferred filters)
        assert call_kwargs.kwargs.get("filters") is None or call_kwargs[1].get("filters") is None

    def test_explicit_filters_override_inferred(self) -> None:
        retriever = _make_mock_retriever([])
        pipeline = GroundedRAGPipeline(retriever)
        explicit = SearchFilters(severity="Low")
        pipeline.retrieve("critical incidents", filters=explicit)
        call_kwargs = retriever.retrieve.call_args
        used_filters = call_kwargs.kwargs.get("filters") or call_kwargs[0][2] if call_kwargs[0] else None
        # Explicit filters passed through
        assert used_filters is not None

    def test_context_text_backward_compat(self) -> None:
        r = _make_search_result("id1", 0.85)
        retriever = _make_mock_retriever([r])
        pipeline = GroundedRAGPipeline(retriever)
        result = pipeline.retrieve("test")
        # context_text comes from the base retriever
        assert result.context_text == "mock context"

    def test_empty_results_produce_no_evidence_message(self) -> None:
        retriever = _make_mock_retriever([])
        pipeline = GroundedRAGPipeline(retriever)
        result = pipeline.retrieve("some query")
        assert "No supporting evidence" in result.grounded_context


# ---------------------------------------------------------------------------
# from_components factory
# ---------------------------------------------------------------------------


class TestFromComponents:
    def test_factory_returns_pipeline_instance(self) -> None:
        from src.embeddings.engine import EmbeddingEngine
        from src.vector_store.qdrant_handler import QdrantHandler
        from qdrant_client import QdrantClient

        mock_engine = MagicMock(spec=EmbeddingEngine)
        mock_engine.dimension = 16
        client = QdrantClient(location=":memory:")
        handler = QdrantHandler(client=client)

        pipeline = GroundedRAGPipeline.from_components(
            embedding_engine=mock_engine,
            qdrant_handler=handler,
        )
        assert isinstance(pipeline, GroundedRAGPipeline)

    def test_factory_with_injected_preprocessor(self) -> None:
        from src.embeddings.engine import EmbeddingEngine
        from src.vector_store.qdrant_handler import QdrantHandler
        from qdrant_client import QdrantClient

        mock_engine = MagicMock(spec=EmbeddingEngine)
        mock_engine.dimension = 16
        client = QdrantClient(location=":memory:")
        handler = QdrantHandler(client=client)
        custom_pp = QueryPreprocessor()

        pipeline = GroundedRAGPipeline.from_components(
            embedding_engine=mock_engine,
            qdrant_handler=handler,
            preprocessor=custom_pp,
        )
        assert pipeline._preprocessor is custom_pp
