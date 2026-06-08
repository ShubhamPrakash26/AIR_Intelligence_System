"""Unit tests for Week 5: vector store metadata extraction and QdrantHandler.

The Qdrant client is never connected to a server in this module.  All client
interactions are satisfied by an in-memory QdrantClient injected via the
``client`` constructor argument, giving us real Qdrant behaviour (collection
creation, upsert, search) without requiring a running process.
"""

from __future__ import annotations

import pytest
from qdrant_client import QdrantClient

from src.models.analysis import VectorMetadata
from src.vector_store.metadata import build_payload, extract_metadata
from src.vector_store.qdrant_handler import QdrantHandler, SearchResult, _to_qdrant_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

DIM = 4  # Tiny dimension for fast in-memory tests


@pytest.fixture()
def in_memory_client() -> QdrantClient:
    """In-memory Qdrant client — no server required."""
    return QdrantClient(location=":memory:")


@pytest.fixture()
def handler(in_memory_client) -> QdrantHandler:
    """QdrantHandler wired to in-memory client with a test collection."""
    h = QdrantHandler(collection_name="test_incidents", client=in_memory_client)
    h.ensure_collection(dimension=DIM)
    return h


@pytest.fixture()
def fake_vector() -> list[float]:
    return [0.1, 0.2, 0.3, 0.4]


# ---------------------------------------------------------------------------
# Metadata extraction tests
# ---------------------------------------------------------------------------


def test_extract_metadata_with_analysis(sample_incident, sample_ai_analysis):
    meta = extract_metadata(sample_incident, sample_ai_analysis)

    assert meta.incident_id == sample_incident.incident_id
    assert meta.severity == sample_ai_analysis.severity
    assert meta.severity_score == sample_ai_analysis.severity_score
    assert meta.root_cause == sample_ai_analysis.root_cause
    assert meta.incident_type == sample_ai_analysis.incident_type
    assert meta.surgery_type == sample_incident.surgery.surgical_branch


def test_extract_metadata_without_analysis_uses_fallback(sample_incident):
    meta = extract_metadata(sample_incident, analysis=None)

    assert meta.incident_id == sample_incident.incident_id
    assert meta.severity_score == 0.0
    assert meta.root_cause == ""
    # Surgery type still resolved from incident
    assert meta.surgery_type == sample_incident.surgery.surgical_branch


def test_extract_metadata_sets_source_from_incident(sample_incident, sample_ai_analysis):
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    assert meta.source == sample_incident.metadata.source_file


def test_extract_metadata_sets_month_and_year(sample_incident, sample_ai_analysis):
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    assert meta.month == "May"
    assert meta.year == 2026


def test_extract_metadata_timestamp_is_iso_string(sample_incident):
    meta = extract_metadata(sample_incident)
    assert "T" in meta.timestamp  # basic ISO-8601 check


# ---------------------------------------------------------------------------
# build_payload tests
# ---------------------------------------------------------------------------


def test_build_payload_returns_dict(sample_vector_metadata):
    payload = build_payload(sample_vector_metadata)
    assert isinstance(payload, dict)


def test_build_payload_contains_required_keys(sample_vector_metadata):
    payload = build_payload(sample_vector_metadata)
    for key in ("incident_id", "severity", "incident_type", "surgery_type"):
        assert key in payload


def test_build_payload_is_json_serialisable(sample_vector_metadata):
    import json

    payload = build_payload(sample_vector_metadata)
    # Must not raise
    json.dumps(payload)


# ---------------------------------------------------------------------------
# _to_qdrant_id helper
# ---------------------------------------------------------------------------


def test_to_qdrant_id_accepts_valid_uuid(sample_incident):
    result = _to_qdrant_id(sample_incident.incident_id)
    assert result == sample_incident.incident_id


def test_to_qdrant_id_rejects_non_uuid():
    with pytest.raises(ValueError):
        _to_qdrant_id("not-a-uuid")


# ---------------------------------------------------------------------------
# QdrantHandler — collection management
# ---------------------------------------------------------------------------


def test_ensure_collection_creates_collection(in_memory_client):
    h = QdrantHandler(collection_name="fresh_col", client=in_memory_client)
    h.ensure_collection(dimension=DIM)
    names = {c.name for c in in_memory_client.get_collections().collections}
    assert "fresh_col" in names


def test_ensure_collection_is_idempotent(in_memory_client):
    h = QdrantHandler(collection_name="idem_col", client=in_memory_client)
    h.ensure_collection(dimension=DIM)
    h.ensure_collection(dimension=DIM)  # second call must not raise


# ---------------------------------------------------------------------------
# QdrantHandler — upsert and retrieval
# ---------------------------------------------------------------------------


def test_upsert_single_stores_point(handler, sample_incident, sample_ai_analysis, fake_vector):
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    handler.upsert(sample_incident.incident_id, fake_vector, meta)

    info = handler.collection_info()
    assert info["points_count"] >= 1


def test_upsert_batch_stores_all_points(handler, sample_incident, sample_ai_analysis):
    from src.utils.helpers import generate_incident_id

    records = []
    for i in range(3):
        iid = generate_incident_id()
        sample_incident.incident_id = iid
        sample_ai_analysis.incident_id = iid
        meta = extract_metadata(sample_incident, sample_ai_analysis)
        vec = [float(i) / 10, 0.2, 0.3, 0.4]
        records.append((iid, vec, meta))

    handler.upsert_batch(records)
    info = handler.collection_info()
    assert info["points_count"] == 3


def test_upsert_batch_empty_is_no_op(handler):
    handler.upsert_batch([])
    info = handler.collection_info()
    assert info["points_count"] == 0


# ---------------------------------------------------------------------------
# QdrantHandler — search
# ---------------------------------------------------------------------------


def test_search_returns_results(handler, sample_incident, sample_ai_analysis, fake_vector):
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    handler.upsert(sample_incident.incident_id, fake_vector, meta)

    results = handler.search(query_vector=fake_vector, top_k=5)

    assert len(results) >= 1
    assert isinstance(results[0], SearchResult)
    assert results[0].incident_id == sample_incident.incident_id
    assert 0.0 <= results[0].score <= 1.01  # cosine can slightly exceed 1.0 due to float precision


def test_search_respects_top_k(handler, sample_incident, sample_ai_analysis):
    from src.utils.helpers import generate_incident_id

    for _ in range(5):
        iid = generate_incident_id()
        sample_incident.incident_id = iid
        sample_ai_analysis.incident_id = iid
        meta = extract_metadata(sample_incident, sample_ai_analysis)
        handler.upsert(iid, [0.1, 0.2, 0.3, 0.4], meta)

    results = handler.search(query_vector=[0.1, 0.2, 0.3, 0.4], top_k=2)
    assert len(results) <= 2


def test_search_result_contains_metadata(handler, sample_incident, sample_ai_analysis, fake_vector):
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    handler.upsert(sample_incident.incident_id, fake_vector, meta)

    results = handler.search(query_vector=fake_vector, top_k=1)
    assert "severity" in results[0].metadata
    assert "incident_type" in results[0].metadata


def test_search_with_severity_filter(handler, sample_incident, sample_ai_analysis):
    from src.utils.helpers import generate_incident_id

    # Upsert one "High" and one "Low" severity incident
    high_id = generate_incident_id()
    low_id = generate_incident_id()

    for iid, severity in [(high_id, "High"), (low_id, "Low")]:
        sample_incident.incident_id = iid
        sample_ai_analysis.incident_id = iid
        sample_ai_analysis.severity = severity
        meta = extract_metadata(sample_incident, sample_ai_analysis)
        handler.upsert(iid, [0.1, 0.2, 0.3, 0.4], meta)

    results = handler.search(
        query_vector=[0.1, 0.2, 0.3, 0.4],
        top_k=5,
        filters={"severity": "High"},
    )
    assert all(r.metadata["severity"] == "High" for r in results)


# ---------------------------------------------------------------------------
# QdrantHandler — delete
# ---------------------------------------------------------------------------


def test_delete_removes_point(handler, sample_incident, sample_ai_analysis, fake_vector):
    meta = extract_metadata(sample_incident, sample_ai_analysis)
    handler.upsert(sample_incident.incident_id, fake_vector, meta)

    handler.delete(sample_incident.incident_id)

    info = handler.collection_info()
    assert info["points_count"] == 0


# ---------------------------------------------------------------------------
# QdrantHandler — collection_info
# ---------------------------------------------------------------------------


def test_collection_info_returns_dict(handler):
    info = handler.collection_info()
    assert isinstance(info, dict)
    assert "name" in info
    assert info["name"] == "test_incidents"
    assert "points_count" in info
