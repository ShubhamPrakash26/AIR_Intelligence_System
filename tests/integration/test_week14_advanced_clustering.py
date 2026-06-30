"""Integration tests for Week 14: Anomaly Detection & Pattern Analysis.

Uses in-memory Qdrant and the deterministic fake embedding model (DIM=32,
no downloads).  Tests the full data path from QdrantHandler.scroll_all()
through AnomalyDetector / PatternAnalyzer to the API Pydantic models.

No real UMAP or HDBSCAN calls — fake models are injected.
"""

from __future__ import annotations

import hashlib
import uuid

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
from src.retrieval.anomaly_detector import AnomalyDetector
from src.retrieval.pattern_analyzer import PatternAnalyzer
from src.vector_store.metadata import extract_metadata
from src.vector_store.qdrant_handler import QdrantHandler

DIM = 32


# ---------------------------------------------------------------------------
# Shared test infrastructure
# ---------------------------------------------------------------------------


class _FakeModel:
    def encode(self, texts, batch_size=32, show_progress_bar=False, normalize_embeddings=True):
        if isinstance(texts, str):
            texts = [texts]
        vecs = []
        for t in texts:
            seed = int(hashlib.md5(t.encode()).hexdigest(), 16) % (2**31)
            rng = np.random.default_rng(seed)
            v = rng.standard_normal(DIM).astype(np.float32)
            v /= np.linalg.norm(v) + 1e-9
            vecs.append(v)
        return np.array(vecs) if len(vecs) > 1 else vecs[0]


def _make_engine() -> EmbeddingEngine:
    eng = EmbeddingEngine(model_name="fake-model", model=_FakeModel())
    eng._dimension = DIM
    return eng


def _make_store() -> QdrantHandler:
    client = QdrantClient(location=":memory:")
    store = QdrantHandler(client=client)
    store.ensure_collection(dimension=DIM)
    return store


def _make_incident(
    suffix: str = "1",
    severity: str = "High",
    surgery: str = "Cardiac",
    year: int = 2026,
    month: str = "March",
    types: list[str] | None = None,
) -> Incident:
    return Incident(
        incident_id=str(uuid.uuid4()),
        patient=PatientInfo(),
        surgery=SurgeryInfo(surgical_branch=surgery),
        anesthesia=AnesthesiaTechnique(),
        incident=IncidentDetails(
            incident_description=f"Clinical incident {suffix}",
            incident_type=types or ["Airway Event"],
        ),
        outcome=OutcomeInfo(harm_severity=severity),
        metadata=ContextMetadata(
            source_file=f"test_{suffix}.xlsx",
            month=month,
            year=year,
        ),
    )


class _IdentityUMAP:
    def fit_transform(self, X):
        return np.array(X)[:, :min(2, np.array(X).shape[1])]


class _LabelHDBSCAN:
    """Assigns labels based on a provided list; fills with 0 if short."""
    def __init__(self, labels):
        self._labels = labels

    def fit_predict(self, X):
        n = len(X)
        labels = list(self._labels) + [0] * max(0, n - len(self._labels))
        return np.array(labels[:n])


# ---------------------------------------------------------------------------
# AnomalyDetector integration
# ---------------------------------------------------------------------------


class TestAnomalyDetectorIntegration:
    def setup_method(self):
        self.engine = _make_engine()
        self.store = _make_store()

        # Ingest 5 incident reports
        for i in range(5):
            inc = _make_incident(str(i), severity="High" if i < 3 else "Low")
            result = self.engine.embed_incident(inc)
            meta = extract_metadata(inc)
            self.store.upsert(inc.incident_id, result.vector, meta)

    def _detector(self, labels):
        return AnomalyDetector(
            umap_model=_IdentityUMAP(),
            hdbscan_model=_LabelHDBSCAN(labels),
        )

    def _records(self):
        return self.store.scroll_all()

    def test_scroll_all_returns_5_records(self):
        assert len(self._records()) == 5

    def test_detect_anomalies_from_scroll_records(self):
        records = self._records()
        detector = self._detector([0, 0, 0, -1, -1])
        result = detector.detect(
            incident_ids=[r["incident_id"] for r in records],
            vectors=[r["vector"] for r in records],
            metadata_list=[r["metadata"] for r in records],
        )
        assert result.n_anomalies == 2
        assert result.total_incidents == 5

    def test_anomaly_ids_are_valid_stored_ids(self):
        records = self._records()
        stored_ids = {r["incident_id"] for r in records}
        detector = self._detector([0, 0, -1, 0, -1])
        result = detector.detect(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        for a in result.anomalies:
            assert a.incident_id in stored_ids

    def test_anomaly_metadata_from_qdrant_payload(self):
        records = self._records()
        detector = self._detector([-1] + [0] * 4)
        result = detector.detect(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        a = result.anomalies[0]
        assert a.surgery_type == "Cardiac"
        assert a.severity in {"High", "Low"}

    def test_zero_anomalies_when_all_clustered(self):
        records = self._records()
        detector = self._detector([0] * 5)
        result = detector.detect(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
        )
        assert result.n_anomalies == 0
        assert result.anomaly_ratio == 0.0

    def test_top_n_respected(self):
        records = self._records()
        detector = self._detector([-1] * 5)
        result = detector.detect(
            [r["incident_id"] for r in records],
            [r["vector"] for r in records],
            [r["metadata"] for r in records],
            top_n=2,
        )
        assert len(result.anomalies) == 2


# ---------------------------------------------------------------------------
# PatternAnalyzer integration
# ---------------------------------------------------------------------------


class TestPatternAnalyzerIntegration:
    def setup_method(self):
        self.engine = _make_engine()
        self.store = _make_store()

        # 3 incidents in 2026/March, 2 in 2026/April, 4 in 2026/May
        combos = [
            (3, 2026, "March", "High", ["Airway Event"]),
            (2, 2026, "April", "Low", ["Medication Error"]),
            (4, 2026, "May", "High", ["Airway Event"]),
        ]
        for count, year, month, sev, types in combos:
            for i in range(count):
                inc = _make_incident(
                    f"{month}_{i}", severity=sev, year=year, month=month, types=types
                )
                result = self.engine.embed_incident(inc)
                meta = extract_metadata(inc)
                self.store.upsert(inc.incident_id, result.vector, meta)

    def _records(self):
        return self.store.scroll_all()

    def test_total_incidents_correct(self):
        result = PatternAnalyzer().analyze(self._records())
        assert result.total_incidents == 9

    def test_period_count(self):
        result = PatternAnalyzer().analyze(self._records())
        assert len(result.periods) == 3

    def test_periods_sorted_chronologically(self):
        result = PatternAnalyzer().analyze(self._records())
        months = [p.month for p in result.periods]
        assert months == ["March", "April", "May"]

    def test_march_count(self):
        result = PatternAnalyzer().analyze(self._records())
        march = next(p for p in result.periods if p.month == "March")
        assert march.count == 3

    def test_april_rate_change_negative(self):
        result = PatternAnalyzer().analyze(self._records())
        april = next(p for p in result.periods if p.month == "April")
        assert april.rate_change_pct is not None
        assert april.rate_change_pct < 0  # 3 → 2 = -33.3%

    def test_may_rate_change_positive(self):
        result = PatternAnalyzer().analyze(self._records())
        may = next(p for p in result.periods if p.month == "May")
        assert may.rate_change_pct is not None
        assert may.rate_change_pct > 0  # 2 → 4 = +100%

    def test_dominant_types_includes_airway_event(self):
        result = PatternAnalyzer().analyze(self._records())
        assert "Airway Event" in result.dominant_incident_types

    def test_trend_direction_is_valid_string(self):
        result = PatternAnalyzer().analyze(self._records())
        assert result.trend_direction in {
            "increasing", "decreasing", "stable", "insufficient_data"
        }

    def test_insight_non_empty(self):
        result = PatternAnalyzer().analyze(self._records())
        assert len(result.insight) > 0

    def test_severity_trend_valid_string(self):
        result = PatternAnalyzer().analyze(self._records())
        assert result.severity_trend in {
            "worsening", "improving", "stable", "insufficient_data"
        }


# ---------------------------------------------------------------------------
# Literature exclusion in PatternAnalyzer
# ---------------------------------------------------------------------------


class TestLiteratureExclusion:
    def setup_method(self):
        from src.models.literature import LiteratureDocument
        from src.vector_store.metadata import extract_literature_metadata

        self.engine = _make_engine()
        self.store = _make_store()

        # 2 incident reports
        for i in range(2):
            inc = _make_incident(str(i), year=2026, month="March")
            result = self.engine.embed_incident(inc)
            meta = extract_metadata(inc)
            self.store.upsert(inc.incident_id, result.vector, meta)

        # 1 literature doc
        doc = LiteratureDocument.create(
            title="NAP4 Airway Report", content="Content.", source_type="literature", year=2011
        )
        result = self.engine.embed_document(doc)
        meta = extract_literature_metadata(doc)
        self.store.upsert(doc.document_id, result.vector, meta)

    def test_pattern_analyzer_excludes_literature(self):
        records = self.store.scroll_all()
        assert len(records) == 3
        result = PatternAnalyzer(exclude_literature=True).analyze(records)
        assert result.total_incidents == 2

    def test_pattern_analyzer_include_literature_counts_all(self):
        records = self.store.scroll_all()
        result = PatternAnalyzer(exclude_literature=False).analyze(records)
        assert result.total_incidents == 3
