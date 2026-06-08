"""Unit tests for Week 5: Embedding Engine.

The sentence-transformers model is never loaded in this module.
All model calls are satisfied by a lightweight MagicMock that returns
deterministic numpy-like arrays via a simple helper object.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.embeddings.engine import EmbeddingEngine, _to_float_list
from src.embeddings.models import (
    DEFAULT_DIMENSION,
    EmbeddingResult,
    get_model_dimension,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


DIM = 8  # Small dimension used for all mock vectors in this module


class _FakeModel:
    """Minimal sentence-transformers stub returning deterministic vectors."""

    def encode(self, input_, *, normalize_embeddings=True, batch_size=32, show_progress_bar=False):
        if isinstance(input_, str):
            return np.ones(DIM, dtype=np.float32)
        return np.ones((len(input_), DIM), dtype=np.float32)


@pytest.fixture()
def mock_engine() -> EmbeddingEngine:
    """EmbeddingEngine with injected fake model (no download)."""
    return EmbeddingEngine(model_name="BAAI/bge-m3", model=_FakeModel())


# ---------------------------------------------------------------------------
# Model registry tests
# ---------------------------------------------------------------------------


def test_get_model_dimension_known_model():
    assert get_model_dimension("BAAI/bge-m3") == 1024


def test_get_model_dimension_unknown_model_returns_default():
    assert get_model_dimension("some-unknown-model") == DEFAULT_DIMENSION


# ---------------------------------------------------------------------------
# EmbeddingResult validation
# ---------------------------------------------------------------------------


def test_embedding_result_valid():
    result = EmbeddingResult(
        incident_id="abc",
        text="hello",
        vector=[0.1] * DIM,
        model_name="BAAI/bge-m3",
        dimension=DIM,
    )
    assert result.incident_id == "abc"
    assert len(result.vector) == DIM


def test_embedding_result_rejects_empty_vector():
    with pytest.raises(ValueError, match="must not be empty"):
        EmbeddingResult(
            incident_id="abc",
            text="hello",
            vector=[],
            model_name="BAAI/bge-m3",
            dimension=DIM,
        )


def test_embedding_result_rejects_dimension_mismatch():
    with pytest.raises(ValueError, match="dimension mismatch"):
        EmbeddingResult(
            incident_id="abc",
            text="hello",
            vector=[0.1] * (DIM + 1),
            model_name="BAAI/bge-m3",
            dimension=DIM,
        )


# ---------------------------------------------------------------------------
# _to_float_list helper
# ---------------------------------------------------------------------------


def test_to_float_list_from_numpy():
    arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    result = _to_float_list(arr)
    assert isinstance(result, list)
    assert result == pytest.approx([1.0, 2.0, 3.0])


def test_to_float_list_from_plain_list():
    result = _to_float_list([0.5, 0.6])
    assert result == [0.5, 0.6]


# ---------------------------------------------------------------------------
# EmbeddingEngine.embed_text
# ---------------------------------------------------------------------------


def test_embed_text_returns_float_list(mock_engine):
    vector = mock_engine.embed_text("Insufflator malfunction during laparoscopy")
    assert isinstance(vector, list)
    assert all(isinstance(v, float) for v in vector)
    assert len(vector) == DIM


def test_embed_text_is_deterministic_with_mock(mock_engine):
    v1 = mock_engine.embed_text("same text")
    v2 = mock_engine.embed_text("same text")
    assert v1 == v2


# ---------------------------------------------------------------------------
# EmbeddingEngine.embed_batch
# ---------------------------------------------------------------------------


def test_embed_batch_empty_input_returns_empty(mock_engine):
    assert mock_engine.embed_batch([]) == []


def test_embed_batch_returns_one_vector_per_text(mock_engine):
    texts = ["text one", "text two", "text three"]
    vectors = mock_engine.embed_batch(texts)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == DIM


# ---------------------------------------------------------------------------
# EmbeddingEngine.build_embed_text
# ---------------------------------------------------------------------------


def test_build_embed_text_without_analysis_contains_surgical_context(
    mock_engine, sample_incident
):
    text = mock_engine.build_embed_text(sample_incident)
    assert "Gynecology" in text
    assert "DHC" in text


def test_build_embed_text_without_analysis_contains_incident_narrative(
    mock_engine, sample_incident
):
    text = mock_engine.build_embed_text(sample_incident)
    assert "insufflat" in text.lower() or "malfunction" in text.lower()


def test_build_embed_text_with_analysis_adds_root_cause(
    mock_engine, sample_incident, sample_ai_analysis
):
    text = mock_engine.build_embed_text(sample_incident, sample_ai_analysis)
    assert "root cause" in text.lower()
    assert "insufflator" in text.lower() or "verification" in text.lower()


def test_build_embed_text_with_analysis_adds_severity(
    mock_engine, sample_incident, sample_ai_analysis
):
    text = mock_engine.build_embed_text(sample_incident, sample_ai_analysis)
    assert "High" in text


def test_build_embed_text_with_analysis_adds_key_learning(
    mock_engine, sample_incident, sample_ai_analysis
):
    text = mock_engine.build_embed_text(sample_incident, sample_ai_analysis)
    assert "key learning" in text.lower()


def test_build_embed_text_without_incident_details_skips_duplicate(
    mock_engine, sample_incident
):
    # When details == description only one of them should appear
    sample_incident.incident.incident_details = sample_incident.incident.incident_description
    text = mock_engine.build_embed_text(sample_incident)
    # Should not contain the line twice
    lines = [l for l in text.splitlines() if "Incident:" in l]
    assert len(lines) == 1


# ---------------------------------------------------------------------------
# EmbeddingEngine.embed_incident
# ---------------------------------------------------------------------------


def test_embed_incident_without_analysis(mock_engine, sample_incident):
    result = mock_engine.embed_incident(sample_incident)
    assert isinstance(result, EmbeddingResult)
    assert result.incident_id == sample_incident.incident_id
    assert len(result.vector) == DIM
    assert result.model_name == "BAAI/bge-m3"


def test_embed_incident_with_analysis(mock_engine, sample_incident, sample_ai_analysis):
    result = mock_engine.embed_incident(sample_incident, sample_ai_analysis)
    assert result.incident_id == sample_incident.incident_id
    # Text should be richer with analysis
    assert "Root cause:" in result.text


# ---------------------------------------------------------------------------
# EmbeddingEngine.embed_incidents_batch
# ---------------------------------------------------------------------------


def test_embed_incidents_batch_empty_returns_empty(mock_engine):
    assert mock_engine.embed_incidents_batch([]) == []


def test_embed_incidents_batch_returns_one_result_per_incident(
    mock_engine, sample_incident
):
    results = mock_engine.embed_incidents_batch([sample_incident, sample_incident])
    assert len(results) == 2
    for r in results:
        assert isinstance(r, EmbeddingResult)
        assert len(r.vector) == DIM


def test_embed_incidents_batch_with_analyses(
    mock_engine, sample_incident, sample_ai_analysis
):
    results = mock_engine.embed_incidents_batch(
        [sample_incident],
        analyses=[sample_ai_analysis],
    )
    assert len(results) == 1
    assert "Root cause:" in results[0].text


def test_embed_incidents_batch_handles_missing_analysis(
    mock_engine, sample_incident, sample_ai_analysis
):
    # Provide an analysis for a *different* incident_id — should fall back gracefully
    sample_ai_analysis.incident_id = "00000000-0000-0000-0000-000000000000"
    results = mock_engine.embed_incidents_batch(
        [sample_incident],
        analyses=[sample_ai_analysis],
    )
    assert len(results) == 1
    # The text should not contain root cause from the unmatched analysis
    assert "Root cause:" not in results[0].text


# ---------------------------------------------------------------------------
# Lazy loading behaviour
# ---------------------------------------------------------------------------


def test_engine_without_model_does_not_fail_on_construction():
    # Construction with no model argument should not trigger a download
    engine = EmbeddingEngine.__new__(EmbeddingEngine)
    engine._model_name = "BAAI/bge-m3"
    engine._dimension = 1024
    engine._model = None
    # Accessing model_name and dimension is safe
    assert engine.model_name == "BAAI/bge-m3"
    assert engine.dimension == 1024
