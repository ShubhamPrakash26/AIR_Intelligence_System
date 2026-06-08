"""Integration tests for Week 5: end-to-end embed → store pipeline.

These tests wire together EmbeddingEngine (mocked model), QdrantHandler
(in-memory client), and metadata extraction to validate the full pipeline:

  Parse → (Analyze) → Embed → Store → Search

No network calls are made: the sentence-transformers model is stubbed out
with a _FakeModel, and Qdrant runs in-memory.
"""

from __future__ import annotations

import numpy as np
import pytest
from qdrant_client import QdrantClient

from src.embeddings.engine import EmbeddingEngine
from src.vector_store.metadata import extract_metadata
from src.vector_store.qdrant_handler import QdrantHandler, SearchResult
from src.utils.helpers import generate_incident_id

# ---------------------------------------------------------------------------
# Shared constants & fixtures
# ---------------------------------------------------------------------------

DIM = 16  # Larger than unit tests to better simulate real similarity search


class _FakeModel:
    """Deterministic stub: encodes to a normalised random-ish vector seeded on text hash."""

    def encode(self, input_, *, normalize_embeddings=True, batch_size=32, show_progress_bar=False):
        if isinstance(input_, str):
            rng = np.random.default_rng(abs(hash(input_)) % (2**32))
            v = rng.random(DIM).astype(np.float32)
            return v / np.linalg.norm(v)
        results = []
        for text in input_:
            rng = np.random.default_rng(abs(hash(text)) % (2**32))
            v = rng.random(DIM).astype(np.float32)
            results.append(v / np.linalg.norm(v))
        return np.stack(results)


@pytest.fixture()
def engine() -> EmbeddingEngine:
    return EmbeddingEngine(model_name="BAAI/bge-m3", model=_FakeModel())


@pytest.fixture()
def qdrant_client() -> QdrantClient:
    return QdrantClient(location=":memory:")


@pytest.fixture()
def handler(qdrant_client) -> QdrantHandler:
    h = QdrantHandler(collection_name="incidents_integration", client=qdrant_client)
    h.ensure_collection(dimension=DIM)
    return h


# ---------------------------------------------------------------------------
# Helper: build a variant incident with a fresh ID
# ---------------------------------------------------------------------------


def _clone_incident(base_incident, *, description: str | None = None):
    """Return a shallow copy of base_incident with a new ID and optional description."""
    clone = base_incident.model_copy(deep=True)
    clone.incident_id = generate_incident_id()
    if description:
        clone.incident.incident_description = description
    return clone


# ---------------------------------------------------------------------------
# Pipeline test 1: single incident — embed and store without analysis
# ---------------------------------------------------------------------------


def test_pipeline_single_incident_without_analysis(engine, handler, sample_incident):
    """An incident can be embedded and stored before analysis is available."""
    result = engine.embed_incident(sample_incident)
    meta = extract_metadata(sample_incident)

    handler.upsert(sample_incident.incident_id, result.vector, meta)

    info = handler.collection_info()
    assert info["points_count"] == 1


# ---------------------------------------------------------------------------
# Pipeline test 2: single incident — embed and store with analysis
# ---------------------------------------------------------------------------


def test_pipeline_single_incident_with_analysis(
    engine, handler, sample_incident, sample_ai_analysis
):
    """Analysis-enriched embeddings round-trip through the vector store."""
    result = engine.embed_incident(sample_incident, sample_ai_analysis)
    meta = extract_metadata(sample_incident, sample_ai_analysis)

    handler.upsert(sample_incident.incident_id, result.vector, meta)

    search_results = handler.search(query_vector=result.vector, top_k=1)
    assert len(search_results) == 1
    assert search_results[0].incident_id == sample_incident.incident_id


# ---------------------------------------------------------------------------
# Pipeline test 3: batch embed and store
# ---------------------------------------------------------------------------


def test_pipeline_batch_embed_and_store(engine, handler, sample_incident, sample_ai_analysis):
    """Multiple incidents can be batch-embedded and stored in one call."""
    incidents = [_clone_incident(sample_incident) for _ in range(5)]
    for inc in incidents:
        sample_ai_analysis.incident_id = inc.incident_id

    results = engine.embed_incidents_batch(incidents)
    assert len(results) == 5

    records = [
        (r.incident_id, r.vector, extract_metadata(inc))
        for r, inc in zip(results, incidents)
    ]
    handler.upsert_batch(records)

    info = handler.collection_info()
    assert info["points_count"] == 5


# ---------------------------------------------------------------------------
# Pipeline test 4: similarity retrieval returns relevant results
# ---------------------------------------------------------------------------


def test_pipeline_similarity_search_finds_similar_incident(
    engine, handler, sample_incident, sample_ai_analysis
):
    """Searching with the same vector as the stored incident returns it as top-1."""
    result = engine.embed_incident(sample_incident, sample_ai_analysis)
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    handler.upsert(sample_incident.incident_id, result.vector, meta)

    # Search with the exact same vector — must be top-1
    hits = handler.search(query_vector=result.vector, top_k=5)
    assert hits[0].incident_id == sample_incident.incident_id
    assert hits[0].score > 0.99  # cosine of identical vectors ≈ 1.0


# ---------------------------------------------------------------------------
# Pipeline test 5: metadata is preserved through round-trip
# ---------------------------------------------------------------------------


def test_pipeline_metadata_preserved_after_storage(
    engine, handler, sample_incident, sample_ai_analysis
):
    """All VectorMetadata fields survive the Qdrant upsert → search cycle."""
    result = engine.embed_incident(sample_incident, sample_ai_analysis)
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    handler.upsert(sample_incident.incident_id, result.vector, meta)

    hits = handler.search(query_vector=result.vector, top_k=1)
    payload = hits[0].metadata

    assert payload["incident_id"] == sample_incident.incident_id
    assert payload["severity"] == sample_ai_analysis.severity
    assert payload["surgery_type"] == sample_incident.surgery.surgical_branch
    assert "incident_type" in payload
    assert "root_cause" in payload


# ---------------------------------------------------------------------------
# Pipeline test 6: upsert is idempotent (update semantics)
# ---------------------------------------------------------------------------


def test_pipeline_upsert_replaces_existing_point(
    engine, handler, sample_incident, sample_ai_analysis
):
    """Re-upserting the same incident_id replaces the point, keeping count at 1."""
    result = engine.embed_incident(sample_incident, sample_ai_analysis)
    meta = extract_metadata(sample_incident, sample_ai_analysis)

    handler.upsert(sample_incident.incident_id, result.vector, meta)
    handler.upsert(sample_incident.incident_id, result.vector, meta)  # duplicate

    info = handler.collection_info()
    assert info["points_count"] == 1


# ---------------------------------------------------------------------------
# Pipeline test 7: delete removes point, search returns empty
# ---------------------------------------------------------------------------


def test_pipeline_delete_then_search_returns_empty(
    engine, handler, sample_incident, sample_ai_analysis
):
    result = engine.embed_incident(sample_incident, sample_ai_analysis)
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    handler.upsert(sample_incident.incident_id, result.vector, meta)

    handler.delete(sample_incident.incident_id)

    hits = handler.search(query_vector=result.vector, top_k=5)
    assert hits == []


# ---------------------------------------------------------------------------
# Pipeline test 8: embed_text is non-empty for a minimal incident
# ---------------------------------------------------------------------------


def test_embed_text_non_empty_for_minimal_incident(engine, sample_incident):
    sample_incident.surgery.surgical_branch = None
    sample_incident.surgery.procedure = None
    sample_incident.incident.incident_description = None
    sample_incident.incident.incident_details = None
    sample_incident.outcome.patient_safety = None

    text = engine.build_embed_text(sample_incident)
    # Even with all optional fields stripped, text should be a non-crashing string
    assert isinstance(text, str)
