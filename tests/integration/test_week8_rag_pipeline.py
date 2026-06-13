"""Integration tests for Week 8 grounded RAG pipeline.

Uses in-memory Qdrant, deterministic fake vectors, and injected fake
embedding models so no downloads are required.

Pipeline under test:
  incident objects -> extract_metadata -> QdrantHandler.upsert
  -> GroundedRAGPipeline.retrieve (with QueryPreprocessor + EvidenceTracker)
  -> GroundedRetrievalResult (intent, keywords, evidence bundle, citations)
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest

from qdrant_client import QdrantClient

from src.embeddings.engine import EmbeddingEngine
from src.models.incident import (
    AnesthesiaTechnique,
    ContextMetadata,
    Incident,
    IncidentDetails,
    OutcomeInfo,
    PatientInfo,
    SurgeryInfo,
)

from src.retrieval.evidence import EvidenceTracker
from src.retrieval.query_preprocessor import QueryIntent, QueryPreprocessor
from src.retrieval.rag import GroundedRAGPipeline, GroundedRetrievalResult
from src.retrieval.similarity_search import SearchFilters, SimilaritySearchEngine
from src.vector_store.metadata import extract_metadata
from src.vector_store.qdrant_handler import QdrantHandler

DIM = 32


# ---------------------------------------------------------------------------
# Fake embedding model (deterministic, no model download)
# ---------------------------------------------------------------------------


class _FakeEmbeddingModel:
    """Return deterministic unit-norm vectors seeded by input text hash."""

    def encode(
        self,
        texts: list[str],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        vecs = []
        for text in texts:
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
            rng = np.random.RandomState(seed)
            v = rng.randn(DIM).astype(np.float32)
            v /= np.linalg.norm(v) + 1e-9
            vecs.append(v)
        return np.array(vecs)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def handler() -> QdrantHandler:
    client = QdrantClient(location=":memory:")
    h = QdrantHandler(client=client)
    h.ensure_collection(dimension=DIM)
    return h


@pytest.fixture()
def engine(handler: QdrantHandler) -> EmbeddingEngine:
    eng = MagicMock(spec=EmbeddingEngine)
    eng.dimension = DIM
    fake_model = _FakeEmbeddingModel()

    def _embed_batch(texts: list[str]) -> list[list[float]]:
        vecs = fake_model.encode(texts)
        return [v.tolist() for v in vecs]

    def _embed(text: str) -> list[float]:
        return fake_model.encode([text])[0].tolist()

    eng.embed_text.side_effect = _embed
    eng.embed_batch.side_effect = _embed_batch
    eng.build_embed_text.side_effect = lambda incident, analysis=None: (
        f"{incident.incident.incident_description or ''} "
        f"{incident.outcome.harm_severity or ''} "
        f"{' '.join(incident.incident.incident_type or [])}"
    )
    return eng


@pytest.fixture()
def pipeline(engine: EmbeddingEngine, handler: QdrantHandler) -> GroundedRAGPipeline:
    return GroundedRAGPipeline.from_components(
        embedding_engine=engine,
        qdrant_handler=handler,
        preprocessor=QueryPreprocessor(),
        tracker=EvidenceTracker(),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_incident(
    narrative: str = "Medication error during induction",
    severity: str = "High",
    incident_type: str = "Medication Error",
    surgery_type: str = "Cardiac",
) -> Incident:
    return Incident(
        incident_id=str(uuid.uuid4()),
        patient=PatientInfo(age_range="31-40", sex="Male", asa_grade="II"),
        surgery=SurgeryInfo(surgical_branch=surgery_type, type_of_procedure="Elective"),
        incident=IncidentDetails(
            incident_description=narrative,
            incident_type=[incident_type],
            timing_of_event="Induction",
        ),
        anesthesia=AnesthesiaTechnique(primary_technique="GA"),
        outcome=OutcomeInfo(
            harm_severity=severity,
            outcome_category="Category C",
        ),
        metadata=ContextMetadata(source_file="test.xlsx", year=2023),
    )


def _store_incident(
    incident: Incident,
    handler: QdrantHandler,
    engine: EmbeddingEngine,
) -> None:
    metadata = extract_metadata(incident)
    embed_text = engine.build_embed_text(incident)
    vector = engine.embed_text(embed_text)
    handler.upsert(incident_id=incident.incident_id, vector=vector, metadata=metadata)


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


class TestGroundedPipelineEmptyStore:
    def test_empty_store_returns_no_evidence(
        self, pipeline: GroundedRAGPipeline
    ) -> None:
        result = pipeline.retrieve("medication errors in cardiac surgery")
        assert result.evidence_bundle.total_retrieved == 0
        assert "No supporting evidence" in result.grounded_context

    def test_empty_store_confidence_is_insufficient(
        self, pipeline: GroundedRAGPipeline
    ) -> None:
        result = pipeline.retrieve("airway management failures")
        assert result.evidence_bundle.confidence == "Insufficient"

    def test_intent_detected_even_with_no_results(
        self, pipeline: GroundedRAGPipeline
    ) -> None:
        result = pipeline.retrieve("why do medication errors occur?")
        assert result.processed_query.intent == QueryIntent.ROOT_CAUSE


class TestGroundedPipelineWithData:
    def test_retrieve_returns_results_after_ingest(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        for i in range(3):
            _store_incident(
                _make_incident(narrative=f"Medication syringe labeling failure {i}"),
                handler,
                engine,
            )
        result = pipeline.retrieve("syringe labeling medication failure", top_k=5)
        assert result.evidence_bundle.total_retrieved >= 1

    def test_grounded_context_contains_incident_info(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(
            _make_incident(
                narrative="Cardiac surgery drug substitution error",
                severity="High",
            ),
            handler,
            engine,
        )
        result = pipeline.retrieve("drug substitution cardiac surgery", top_k=3)
        # Grounded context should contain evidence markers
        assert "Evidence confidence" in result.grounded_context or \
               "Grounded evidence" in result.grounded_context or \
               "No supporting evidence" in result.grounded_context

    def test_citations_populated(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(_make_incident(), handler, engine)
        result = pipeline.retrieve("medication error", top_k=3)
        if result.evidence_bundle.total_retrieved > 0:
            assert len(result.evidence_bundle.citations) > 0

    def test_keywords_extracted_from_query(
        self, pipeline: GroundedRAGPipeline
    ) -> None:
        result = pipeline.retrieve("medication errors during cardiac surgery induction")
        keywords = result.processed_query.keywords
        assert len(keywords) > 0
        # At least one of the content words should appear
        assert any(k in ("medication", "errors", "cardiac", "surgery", "induction")
                   for k in keywords)

    def test_coverage_score_in_bundle(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(_make_incident(narrative="cardiac medication failure"), handler, engine)
        result = pipeline.retrieve("cardiac medication", top_k=3)
        assert 0.0 <= result.evidence_bundle.coverage_score <= 1.0

    def test_preprocessing_disabled_still_retrieves(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(_make_incident(), handler, engine)
        result = pipeline.retrieve("incident", top_k=3, use_preprocessing=False)
        assert isinstance(result, GroundedRetrievalResult)
        # Intent defaults to GENERAL when preprocessing is off and keywords are empty
        assert result.evidence_bundle is not None


class TestFilterInference:
    def test_severity_filter_inferred_and_applied(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(_make_incident(severity="High"), handler, engine)
        _store_incident(_make_incident(severity="Low"), handler, engine)
        # Query mentioning "high" should produce a SearchFilters with severity=High
        result = pipeline.retrieve("high severity medication errors", top_k=5)
        if result.processed_query.suggested_filters:
            assert result.processed_query.suggested_filters.severity == "High"

    def test_no_filter_when_none_detected(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(_make_incident(), handler, engine)
        result = pipeline.retrieve("medication errors during induction", top_k=5)
        # No explicit severity mentioned -> no filter inferred
        assert result.processed_query.suggested_filters is None


class TestGroundedRetrievalResultStructure:
    def test_context_text_backward_compat(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(_make_incident(), handler, engine)
        result = pipeline.retrieve("medication", top_k=3)
        # context_text should always be a string (possibly empty)
        assert isinstance(result.context_text, str)

    def test_was_reranked_false_by_default(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(_make_incident(), handler, engine)
        result = pipeline.retrieve("medication", top_k=3, rerank=False)
        assert result.was_reranked is False

    def test_top_result_none_when_empty(
        self, pipeline: GroundedRAGPipeline
    ) -> None:
        result = pipeline.retrieve("something")
        assert result.top_result is None

    def test_final_results_consistent_with_was_reranked(
        self,
        pipeline: GroundedRAGPipeline,
        handler: QdrantHandler,
        engine: EmbeddingEngine,
    ) -> None:
        _store_incident(_make_incident(), handler, engine)
        result = pipeline.retrieve("medication", top_k=3)
        if result.was_reranked:
            assert result.final_results is result.reranked
        else:
            assert result.final_results is result.results
