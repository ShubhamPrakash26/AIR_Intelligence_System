"""Integration tests for the Week 7 clustering pipeline.

Uses in-memory Qdrant, deterministic fake vectors, and injected fake
UMAP/HDBSCAN models so no downloads are required.

Pipeline under test:
  incident objects -> extract_metadata -> QdrantHandler.upsert
  -> QdrantHandler.scroll_all
  -> IncidentClusteringEngine.cluster
  -> ClusteringResult
"""

from __future__ import annotations

import uuid

import numpy as np
import pytest

from qdrant_client import QdrantClient

from src.models.incident import (
    AnesthesiaTechnique,
    ContextMetadata,
    Incident,
    IncidentDetails,
    OutcomeInfo,
    PatientInfo,
    SurgeryInfo,
)
from src.retrieval.clustering import ClusteringResult, IncidentClusteringEngine
from src.vector_store.metadata import extract_metadata
from src.vector_store.qdrant_handler import QdrantHandler

DIM = 16


# ---------------------------------------------------------------------------
# Fake models
# ---------------------------------------------------------------------------


class _FakeUMAP:
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        return X[:, :2].astype(np.float32)


class _FakeHDBSCAN:
    """Label 0 if first coord >= 0, else label 1."""

    def fit_predict(self, X: np.ndarray) -> np.ndarray:
        return np.array([0 if float(x[0]) >= 0 else 1 for x in X])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_vec(seed: int, positive: bool = True) -> list[float]:
    rng = np.random.RandomState(seed)
    v = rng.uniform(0.3, 1.0, DIM).astype(np.float32).tolist()
    if not positive:
        v[0] = -abs(v[0])
    return v


def _make_incident(surgery: str = "Colorectal", severity: str = "High") -> Incident:
    return Incident(
        incident_id=str(uuid.uuid4()),
        patient=PatientInfo(),
        surgery=SurgeryInfo(surgical_branch=surgery),
        incident=IncidentDetails(
            incident_type=["Airway"],
            incident_description="Test incident for clustering integration tests.",
        ),
        anesthesia=AnesthesiaTechnique(),
        outcome=OutcomeInfo(harm_severity=severity),
        metadata=ContextMetadata(),
    )


def _make_store() -> QdrantHandler:
    client = QdrantClient(location=":memory:")
    store = QdrantHandler(client=client)
    store.ensure_collection(dimension=DIM)
    return store


def _engine() -> IncidentClusteringEngine:
    return IncidentClusteringEngine(
        min_cluster_size=2,
        umap_model=_FakeUMAP(),
        hdbscan_model=_FakeHDBSCAN(),
    )


def _populate(store: QdrantHandler, n: int = 6) -> list[str]:
    """Upsert n incidents: first half positive first coord, second half negative."""
    ids = []
    for i in range(n):
        incident = _make_incident()
        vec = _make_vec(i, positive=(i < n // 2))
        metadata = extract_metadata(incident)
        store.upsert(incident.incident_id, vec, metadata)
        ids.append(incident.incident_id)
    return ids


# ---------------------------------------------------------------------------
# scroll_all tests
# ---------------------------------------------------------------------------


class TestScrollAll:
    def test_returns_all_stored(self):
        store = _make_store()
        ids = _populate(store, n=4)
        records = store.scroll_all()
        assert len(records) == 4

    def test_record_has_required_keys(self):
        store = _make_store()
        incident = _make_incident()
        store.upsert(incident.incident_id, _make_vec(0), extract_metadata(incident))
        records = store.scroll_all()
        assert len(records) == 1
        assert "incident_id" in records[0]
        assert "vector" in records[0]
        assert "metadata" in records[0]

    def test_vector_length_matches_dim(self):
        store = _make_store()
        incident = _make_incident()
        store.upsert(incident.incident_id, _make_vec(0), extract_metadata(incident))
        records = store.scroll_all()
        assert len(records[0]["vector"]) == DIM

    def test_incident_id_matches(self):
        store = _make_store()
        incident = _make_incident()
        store.upsert(incident.incident_id, _make_vec(0), extract_metadata(incident))
        records = store.scroll_all()
        assert records[0]["incident_id"] == incident.incident_id

    def test_empty_collection(self):
        store = _make_store()
        records = store.scroll_all()
        assert records == []


# ---------------------------------------------------------------------------
# Full clustering pipeline
# ---------------------------------------------------------------------------


class TestClusteringPipeline:
    def test_returns_clustering_result(self):
        store = _make_store()
        _populate(store, n=6)
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        assert isinstance(result, ClusteringResult)

    def test_total_incidents_correct(self):
        store = _make_store()
        _populate(store, n=6)
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        assert result.total_incidents == 6

    def test_two_clusters_identified(self):
        store = _make_store()
        _populate(store, n=6)
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        assert result.n_clusters == 2

    def test_all_incident_ids_accounted_for(self):
        store = _make_store()
        original_ids = set(_populate(store, n=6))
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        assigned = {iid for t in result.themes for iid in t.incident_ids}
        all_found = assigned | set(result.noise_incident_ids)
        assert all_found == original_ids

    def test_umap_coords_all_incidents(self):
        store = _make_store()
        _populate(store, n=4)
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        assert len(result.umap_coords) == 4

    def test_theme_names_nonempty(self):
        store = _make_store()
        _populate(store, n=6)
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        for theme in result.themes:
            assert len(theme.theme_name) > 0

    def test_theme_recommendations_nonempty(self):
        store = _make_store()
        _populate(store, n=6)
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        for theme in result.themes:
            assert len(theme.recommendations) >= 1

    def test_summary_report_generated(self):
        store = _make_store()
        _populate(store, n=4)
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        report = result.summary_report()
        assert "Clustering Report" in report
        assert "incidents" in report

    def test_theme_extractor_in_pipeline(self):
        class _FakeExtractor:
            def name_theme(self, metadata_list):
                return "Pipeline Theme", "Pipeline insight.", ["Pipeline rec."]

        store = _make_store()
        _populate(store, n=6)
        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
            theme_extractor=_FakeExtractor(),
        )
        for theme in result.themes:
            assert theme.theme_name == "Pipeline Theme"

    def test_empty_store_returns_empty_result(self):
        result = _engine().cluster([], [], [])
        assert result.total_incidents == 0
        assert result.n_clusters == 0

    def test_metadata_preserved_in_themes(self):
        store = _make_store()
        # All positive — all will be cluster 0
        for i in range(4):
            incident = _make_incident(severity="Critical")
            store.upsert(incident.incident_id, _make_vec(i, positive=True), extract_metadata(incident))
        # All negative — all will be cluster 1
        for i in range(4, 8):
            incident = _make_incident(severity="Low")
            store.upsert(incident.incident_id, _make_vec(i, positive=False), extract_metadata(incident))

        records = store.scroll_all()
        result = _engine().cluster(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        assert result.n_clusters == 2
        for theme in result.themes:
            assert len(theme.patterns) >= 1
