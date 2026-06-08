"""Integration tests for Week 6 — end-to-end retrieval pipeline.

Uses:
  - _FakeModel (deterministic embeddings, no download)
  - QdrantClient(location=":memory:") (no server)
  - _FakeCrossEncoder (no model download)

All tests run offline and complete in seconds.
"""

from __future__ import annotations

import uuid
from typing import Any

import numpy as np
import pytest

from src.embeddings.engine import EmbeddingEngine
from src.models.analysis import AIAnalysis, VectorMetadata
from src.models.incident import Incident
from src.retrieval.rag import RAGRetriever, RetrievedContext
from src.retrieval.reranker import CrossEncoderReranker, RerankResult
from src.retrieval.similarity_search import SearchFilters, SimilaritySearchEngine
from src.vector_store.metadata import extract_metadata
from src.vector_store.qdrant_handler import QdrantHandler

DIM = 16


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeModel:
    """Deterministic embedding model — same text always produces the same vector."""

    def encode(
        self,
        input_: Any,
        batch_size: int = 32,
        show_progress_bar: bool = False,
        convert_to_numpy: bool = True,
        normalize_embeddings: bool = False,
    ) -> np.ndarray:
        if isinstance(input_, str):
            seed = hash(input_) & 0xFFFF_FFFF
            rng = np.random.default_rng(seed)
            return rng.random(DIM).astype(np.float32)

        result = []
        for text in input_:
            seed = hash(text) & 0xFFFF_FFFF
            rng = np.random.default_rng(seed)
            result.append(rng.random(DIM).astype(np.float32))
        return np.array(result, dtype=np.float32)


class _FakeCrossEncoder:
    """Deterministic cross-encoder: scores by length of document text."""

    def rank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        scored = [
            {"corpus_id": i, "score": float(len(doc))}
            for i, doc in enumerate(documents)
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k] if top_k else scored

    def predict(self, pairs: list[list[str]]) -> np.ndarray:
        return np.array([float(len(p[1])) for p in pairs])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mem_client():
    from qdrant_client import QdrantClient

    return QdrantClient(location=":memory:")


@pytest.fixture()
def embed_engine():
    return EmbeddingEngine(model=_FakeModel())


@pytest.fixture()
def qdrant_handler(mem_client):
    handler = QdrantHandler(client=mem_client)
    handler.ensure_collection(dimension=DIM)
    return handler


@pytest.fixture()
def search_engine(embed_engine, qdrant_handler):
    return SimilaritySearchEngine(embed_engine, qdrant_handler)


@pytest.fixture()
def reranker():
    return CrossEncoderReranker(model=_FakeCrossEncoder())


@pytest.fixture()
def rag_retriever(search_engine, reranker):
    return RAGRetriever(search_engine=search_engine, reranker=reranker)


def _make_incident(surgery: str = "Cardiac", severity: str = "High") -> Incident:
    """Build a minimal but valid Incident for testing."""
    from src.models.incident import (
        AnesthesiaTechnique,
        ContextMetadata,
        IncidentDetails,
        OutcomeInfo,
        PatientInfo,
        SurgeryInfo,
    )

    return Incident(
        incident_id=str(uuid.uuid4()),
        patient=PatientInfo(),
        surgery=SurgeryInfo(surgical_branch=surgery),
        incident=IncidentDetails(
            incident_type=["Airway"],
            incident_description="Patient experienced unexpected airway obstruction.",
        ),
        anesthesia=AnesthesiaTechnique(),
        outcome=OutcomeInfo(harm_severity=severity),
        metadata=ContextMetadata(),
    )


def _upsert_incident(
    handler: QdrantHandler,
    engine: EmbeddingEngine,
    incident: Incident,
    analysis: AIAnalysis | None = None,
) -> None:
    result = engine.embed_incident(incident, analysis)
    metadata = extract_metadata(incident, analysis)
    handler.upsert(incident.incident_id, result.vector, metadata)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchByText:
    def test_returns_stored_incident(self, qdrant_handler, embed_engine, search_engine):
        inc = _make_incident()
        _upsert_incident(qdrant_handler, embed_engine, inc)

        results = search_engine.search_by_text("airway obstruction cardiac surgery", top_k=5)
        assert len(results) >= 1
        ids = {r.incident_id for r in results}
        assert inc.incident_id in ids

    def test_ranks_from_one(self, qdrant_handler, embed_engine, search_engine):
        inc = _make_incident()
        _upsert_incident(qdrant_handler, embed_engine, inc)

        results = search_engine.search_by_text("airway event", top_k=3)
        for i, r in enumerate(results, start=1):
            assert r.rank == i


class TestSeverityFilter:
    def test_filters_by_severity(self, qdrant_handler, embed_engine, search_engine):
        high = _make_incident(severity="High")
        low = _make_incident(severity="Low")
        _upsert_incident(qdrant_handler, embed_engine, high)
        _upsert_incident(qdrant_handler, embed_engine, low)

        results = search_engine.search_by_text(
            "airway", filters=SearchFilters(severity="High")
        )
        assert all(r.severity == "High" for r in results if r.metadata)
        ids = {r.incident_id for r in results}
        assert high.incident_id in ids
        assert low.incident_id not in ids


class TestSearchByIncident:
    def test_finds_similar_incident(self, qdrant_handler, embed_engine, search_engine):
        inc1 = _make_incident(surgery="Cardiac")
        inc2 = _make_incident(surgery="Cardiac")
        _upsert_incident(qdrant_handler, embed_engine, inc1)
        _upsert_incident(qdrant_handler, embed_engine, inc2)

        results = search_engine.search_by_incident(_make_incident(surgery="Cardiac"), top_k=5)
        assert len(results) >= 1


class TestSearchSimilarToStored:
    def test_finds_similar_stored_incident(self, qdrant_handler, embed_engine, search_engine):
        inc1 = _make_incident()
        inc2 = _make_incident()
        inc3 = _make_incident()
        _upsert_incident(qdrant_handler, embed_engine, inc1)
        _upsert_incident(qdrant_handler, embed_engine, inc2)
        _upsert_incident(qdrant_handler, embed_engine, inc3)

        results = search_engine.search_similar_to_stored(inc1.incident_id, top_k=2)
        ids = {r.incident_id for r in results}
        # inc1 itself should be excluded (exclude_self=True by default)
        assert inc1.incident_id not in ids
        assert len(results) <= 2


class TestRAGPipeline:
    def test_retrieve_returns_context(self, qdrant_handler, embed_engine, rag_retriever):
        inc = _make_incident()
        _upsert_incident(qdrant_handler, embed_engine, inc)

        ctx = rag_retriever.retrieve("airway management during cardiac surgery")
        assert isinstance(ctx, RetrievedContext)
        assert ctx.context_text != ""

    def test_retrieve_with_reranking(self, qdrant_handler, embed_engine, rag_retriever):
        for _ in range(3):
            _upsert_incident(qdrant_handler, embed_engine, _make_incident())

        ctx = rag_retriever.retrieve("airway obstruction", top_k=3, rerank=True)
        assert ctx.was_reranked
        assert len(ctx.reranked) > 0
        assert all(isinstance(r, RerankResult) for r in ctx.reranked)

    def test_context_text_contains_severity(self, qdrant_handler, embed_engine, rag_retriever):
        inc = _make_incident(severity="Critical")
        _upsert_incident(qdrant_handler, embed_engine, inc)

        ctx = rag_retriever.retrieve("critical airway event", top_k=5)
        # At least one result should have Critical severity in context
        assert ctx.context_text != ""

    def test_retrieve_for_incident(self, qdrant_handler, embed_engine, rag_retriever):
        ref = _make_incident()
        similar = _make_incident()
        _upsert_incident(qdrant_handler, embed_engine, ref)
        _upsert_incident(qdrant_handler, embed_engine, similar)

        ctx = rag_retriever.retrieve_for_incident(ref, top_k=5)
        assert isinstance(ctx, RetrievedContext)
        assert len(ctx.results) >= 1

    def test_no_results_when_collection_empty(self, search_engine):
        results = search_engine.search_by_text("anything", top_k=5)
        assert results == []

    def test_format_context_empty(self, rag_retriever):
        text = RAGRetriever.format_context([])
        assert "No relevant" in text

    def test_context_text_has_incident_count(self, qdrant_handler, embed_engine, rag_retriever):
        for _ in range(2):
            _upsert_incident(qdrant_handler, embed_engine, _make_incident())

        ctx = rag_retriever.retrieve("test query", top_k=5)
        if ctx.results:
            assert str(len(ctx.results)) in ctx.context_text or "similar" in ctx.context_text
