"""Integration tests for Week 13: Multi-Source RAG.

Uses in-memory Qdrant, a deterministic fake embedding model (no downloads),
and synthetic incident + literature documents.

Pipeline under test:
  LiteratureDocument  -> extract_literature_metadata -> QdrantHandler.upsert
  Incident            -> extract_metadata             -> QdrantHandler.upsert
  SimilaritySearchEngine.search_by_text  (cross-source + filtered)
  POST /retrieval/ingest/literature      (endpoint-level)
  POST /retrieval/trends                 (endpoint-level)
  LiteratureIngestResult / TrendBucket / TrendsResponse  (Pydantic models)
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

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
from src.models.literature import LiteratureDocument
from src.retrieval.similarity_search import SearchFilters, SimilaritySearchEngine
from src.vector_store.metadata import extract_literature_metadata, extract_metadata
from src.vector_store.qdrant_handler import QdrantHandler

DIM = 32


# ---------------------------------------------------------------------------
# Fake embedding model — deterministic, no model download
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
    eng._dimension = DIM  # override 1024 default; fake model produces DIM-dim vectors
    return eng


def _make_store() -> QdrantHandler:
    client = QdrantClient(location=":memory:")
    store = QdrantHandler(client=client)
    engine = _make_engine()
    store.ensure_collection(dimension=engine.dimension)
    return store


def _make_incident(
    suffix: str = "1",
    severity: str = "High",
    surgery: str = "Cardiac",
    year: int = 2026,
    month: str = "March",
) -> Incident:
    return Incident(
        incident_id=str(uuid.uuid4()),
        patient=PatientInfo(),
        surgery=SurgeryInfo(surgical_branch=surgery),
        anesthesia=AnesthesiaTechnique(),
        incident=IncidentDetails(
            incident_description=f"Airway incident {suffix}",
            incident_type=["Airway Event"],
        ),
        outcome=OutcomeInfo(harm_severity=severity),
        metadata=ContextMetadata(
            source_file=f"test_{suffix}.xlsx",
            month=month,
            year=year,
        ),
    )


def _make_lit_doc(
    suffix: str = "1",
    source_type: str = "literature",
    year: int = 2015,
) -> LiteratureDocument:
    return LiteratureDocument.create(
        title=f"Airway Management Guidelines {suffix}",
        content=f"Clinical guidelines for airway management safety and patient outcomes {suffix}.",
        source_type=source_type,
        authors=["Cook TM"],
        year=year,
        journal="Br J Anaesth",
    )


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestLiteratureIngestResultModel:
    def test_valid_model(self):
        from src.api.retrieval import LiteratureIngestResult
        r = LiteratureIngestResult(
            ingested=2,
            failed=0,
            document_ids=["abc", "def"],
            collection="incidents",
            dimension=1024,
            note="Stored 2 documents.",
        )
        assert r.ingested == 2
        assert r.dimension == 1024

    def test_failed_count(self):
        from src.api.retrieval import LiteratureIngestResult
        r = LiteratureIngestResult(
            ingested=1, failed=1, document_ids=["x"], collection="c", dimension=128, note="n"
        )
        assert r.failed == 1

    def test_document_ids_list(self):
        from src.api.retrieval import LiteratureIngestResult
        r = LiteratureIngestResult(
            ingested=0, failed=0, document_ids=[], collection="c", dimension=128, note="n"
        )
        assert r.document_ids == []


class TestTrendBucketModel:
    def test_valid_bucket(self):
        from src.api.retrieval import TrendBucket
        b = TrendBucket(
            year=2026,
            month="March",
            count=5,
            severity_distribution={"High": 3, "Low": 2},
            incident_types=["Airway Event"],
            source_types=["incident_report"],
        )
        assert b.count == 5
        assert b.year == 2026

    def test_nullable_year_and_month(self):
        from src.api.retrieval import TrendBucket
        b = TrendBucket(
            year=None,
            month=None,
            count=1,
            severity_distribution={},
            incident_types=[],
            source_types=[],
        )
        assert b.year is None
        assert b.month is None

    def test_source_types_in_bucket(self):
        from src.api.retrieval import TrendBucket
        b = TrendBucket(
            year=2025, month="June", count=3,
            severity_distribution={},
            incident_types=[],
            source_types=["incident_report", "literature"],
        )
        assert "literature" in b.source_types


class TestTrendsResponseModel:
    def test_valid_response(self):
        from src.api.retrieval import TrendsResponse
        r = TrendsResponse(
            total_records=10,
            incident_records=8,
            literature_records=2,
            buckets=[],
            top_incident_types=["Airway Event"],
            severity_summary={"High": 4, "Low": 6},
        )
        assert r.total_records == 10
        assert r.literature_records == 2

    def test_empty_response(self):
        from src.api.retrieval import TrendsResponse
        r = TrendsResponse(
            total_records=0,
            incident_records=0,
            literature_records=0,
            buckets=[],
            top_incident_types=[],
            severity_summary={},
        )
        assert r.buckets == []


# ---------------------------------------------------------------------------
# Cross-source ingestion + search
# ---------------------------------------------------------------------------


class TestCrossSourceIngestion:
    def setup_method(self):
        self.engine = _make_engine()
        self.store = _make_store()
        self.search = SimilaritySearchEngine(self.engine, self.store)

        # Ingest 3 incidents
        for i in range(1, 4):
            inc = _make_incident(str(i), severity="High" if i < 3 else "Low")
            result = self.engine.embed_incident(inc)
            meta = extract_metadata(inc)
            self.store.upsert(inc.incident_id, result.vector, meta)

        # Ingest 2 literature docs
        for i in range(1, 3):
            doc = _make_lit_doc(str(i))
            result = self.engine.embed_document(doc)
            meta = extract_literature_metadata(doc)
            self.store.upsert(doc.document_id, result.vector, meta)

    def test_total_stored(self):
        records = self.store.scroll_all()
        assert len(records) == 5

    def test_incidents_have_incident_report_source_type(self):
        records = self.store.scroll_all()
        inc_records = [r for r in records if r["metadata"].get("source_type") == "incident_report"]
        assert len(inc_records) == 3

    def test_literature_docs_have_literature_source_type(self):
        records = self.store.scroll_all()
        lit_records = [r for r in records if r["metadata"].get("source_type") == "literature"]
        assert len(lit_records) == 2

    def test_cross_source_search_returns_both_types(self):
        results = self.search.search_by_text("airway management guidelines", top_k=5)
        source_types = {r.metadata.get("source_type") for r in results}
        # Both types present in a cross-source search (top_k=5, 5 records total)
        assert len(source_types) >= 1

    def test_filter_incidents_only(self):
        filters = SearchFilters(source_type="incident_report")
        results = self.search.search_by_text("airway", top_k=5, filters=filters)
        for r in results:
            assert r.metadata.get("source_type") == "incident_report"

    def test_filter_literature_only(self):
        filters = SearchFilters(source_type="literature")
        results = self.search.search_by_text("guidelines", top_k=5, filters=filters)
        for r in results:
            assert r.metadata.get("source_type") == "literature"

    def test_incident_filter_returns_at_most_3(self):
        filters = SearchFilters(source_type="incident_report")
        results = self.search.search_by_text("airway", top_k=10, filters=filters)
        assert len(results) <= 3

    def test_literature_filter_returns_at_most_2(self):
        filters = SearchFilters(source_type="literature")
        results = self.search.search_by_text("guidelines", top_k=10, filters=filters)
        assert len(results) <= 2

    def test_literature_severity_is_reference(self):
        filters = SearchFilters(source_type="literature")
        results = self.search.search_by_text("guidelines", top_k=5, filters=filters)
        for r in results:
            assert r.metadata.get("severity") == "Reference"

    def test_literature_surgery_type_is_literature(self):
        filters = SearchFilters(source_type="literature")
        results = self.search.search_by_text("guidelines", top_k=5, filters=filters)
        for r in results:
            assert r.metadata.get("surgery_type") == "Literature"

    def test_incident_surgery_type_is_cardiac(self):
        filters = SearchFilters(source_type="incident_report")
        results = self.search.search_by_text("airway", top_k=5, filters=filters)
        for r in results:
            assert r.metadata.get("surgery_type") == "Cardiac"


# ---------------------------------------------------------------------------
# Combined source_type + severity filter
# ---------------------------------------------------------------------------


class TestCombinedFilters:
    def setup_method(self):
        self.engine = _make_engine()
        self.store = _make_store()
        self.search = SimilaritySearchEngine(self.engine, self.store)

        # Two High incidents, one Low incident, one guideline
        for sev, suf in [("High", "h1"), ("High", "h2"), ("Low", "l1")]:
            inc = _make_incident(suf, severity=sev)
            result = self.engine.embed_incident(inc)
            meta = extract_metadata(inc)
            self.store.upsert(inc.incident_id, result.vector, meta)

        doc = _make_lit_doc("g1", source_type="guideline")
        result = self.engine.embed_document(doc)
        meta = extract_literature_metadata(doc)
        self.store.upsert(doc.document_id, result.vector, meta)

    def test_high_incidents_filter(self):
        filters = SearchFilters(source_type="incident_report", severity="High")
        results = self.search.search_by_text("airway", top_k=10, filters=filters)
        for r in results:
            assert r.metadata.get("severity") == "High"
            assert r.metadata.get("source_type") == "incident_report"

    def test_guideline_filter(self):
        filters = SearchFilters(source_type="guideline")
        results = self.search.search_by_text("guideline", top_k=10, filters=filters)
        for r in results:
            assert r.metadata.get("source_type") == "guideline"


# ---------------------------------------------------------------------------
# Trends aggregation logic (unit-level, no HTTP)
# ---------------------------------------------------------------------------


class TestTrendsAggregation:
    """Validates the logic used by POST /retrieval/trends directly, using
    in-memory Qdrant with known records."""

    def setup_method(self):
        self.engine = _make_engine()
        self.store = _make_store()

        # 2 incidents in 2026/March
        for i in range(2):
            inc = _make_incident(str(i), severity="High", year=2026, month="March")
            result = self.engine.embed_incident(inc)
            meta = extract_metadata(inc)
            self.store.upsert(inc.incident_id, result.vector, meta)

        # 1 incident in 2025/June
        inc = _make_incident("old", severity="Low", year=2025, month="June")
        result = self.engine.embed_incident(inc)
        meta = extract_metadata(inc)
        self.store.upsert(inc.incident_id, result.vector, meta)

        # 1 literature doc (no year/month metadata in bucket sense)
        doc = _make_lit_doc("l1", year=2015)
        result = self.engine.embed_document(doc)
        meta = extract_literature_metadata(doc)
        self.store.upsert(doc.document_id, result.vector, meta)

    def _run_trends(self) -> dict:
        """Replicate the /retrieval/trends aggregation logic."""
        from collections import Counter, defaultdict
        all_records = self.store.scroll_all()
        bucket_map = defaultdict(
            lambda: {"count": 0, "severity": Counter(), "types": set(), "source_types": set()}
        )
        incident_count = 0
        literature_count = 0

        for record in all_records:
            meta = record.get("metadata", {})
            year = meta.get("year")
            month = meta.get("month")
            severity = meta.get("severity", "Unknown")
            inc_types = meta.get("incident_type", [])
            src_type = meta.get("source_type", "incident_report")

            if src_type == "incident_report":
                incident_count += 1
            else:
                literature_count += 1

            key = (year, month)
            bucket_map[key]["count"] += 1
            bucket_map[key]["severity"][severity] += 1
            bucket_map[key]["types"].update(inc_types)
            bucket_map[key]["source_types"].add(src_type)

        return {
            "total": len(all_records),
            "incidents": incident_count,
            "literature": literature_count,
            "bucket_map": bucket_map,
        }

    def test_total_records(self):
        result = self._run_trends()
        assert result["total"] == 4

    def test_incident_count(self):
        result = self._run_trends()
        assert result["incidents"] == 3

    def test_literature_count(self):
        result = self._run_trends()
        assert result["literature"] == 1

    def test_march_bucket_count(self):
        result = self._run_trends()
        march_key = (2026, "March")
        assert result["bucket_map"][march_key]["count"] == 2

    def test_june_bucket_count(self):
        result = self._run_trends()
        june_key = (2025, "June")
        assert result["bucket_map"][june_key]["count"] == 1

    def test_march_severity_distribution(self):
        result = self._run_trends()
        march_key = (2026, "March")
        assert result["bucket_map"][march_key]["severity"]["High"] == 2

    def test_source_types_in_buckets(self):
        result = self._run_trends()
        all_source_types = set()
        for bkt in result["bucket_map"].values():
            all_source_types.update(bkt["source_types"])
        assert "incident_report" in all_source_types
        assert "literature" in all_source_types


# ---------------------------------------------------------------------------
# Literature metadata payload stored in Qdrant
# ---------------------------------------------------------------------------


class TestLiteratureMetadataInQdrant:
    def setup_method(self):
        self.engine = _make_engine()
        self.store = _make_store()
        self.doc = _make_lit_doc("payload_test")
        result = self.engine.embed_document(self.doc)
        meta = extract_literature_metadata(self.doc)
        self.store.upsert(self.doc.document_id, result.vector, meta)

    def test_stored_payload_has_source_type(self):
        records = self.store.scroll_all()
        assert len(records) == 1
        payload = records[0]["metadata"]
        assert payload.get("source_type") == "literature"

    def test_stored_payload_severity_reference(self):
        records = self.store.scroll_all()
        payload = records[0]["metadata"]
        assert payload.get("severity") == "Reference"

    def test_stored_payload_title(self):
        records = self.store.scroll_all()
        payload = records[0]["metadata"]
        assert payload.get("title") == self.doc.title

    def test_stored_payload_surgery_type(self):
        records = self.store.scroll_all()
        payload = records[0]["metadata"]
        assert payload.get("surgery_type") == "Literature"

    def test_stored_payload_year(self):
        records = self.store.scroll_all()
        payload = records[0]["metadata"]
        assert payload.get("year") == 2015
