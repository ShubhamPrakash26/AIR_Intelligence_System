"""Unit tests for Week 6 — SimilaritySearchEngine and SearchFilters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from src.retrieval.similarity_search import (
    SearchFilters,
    SimilaritySearchEngine,
    SimilaritySearchResult,
    _apply_python_filter,
    _rank,
)
from src.vector_store.qdrant_handler import SearchResult


# ---------------------------------------------------------------------------
# SearchFilters
# ---------------------------------------------------------------------------


class TestSearchFilters:
    def test_empty_when_all_none(self):
        f = SearchFilters()
        assert f.is_empty()

    def test_not_empty_when_any_set(self):
        assert not SearchFilters(severity="High").is_empty()
        assert not SearchFilters(surgery_type="Cardiac").is_empty()
        assert not SearchFilters(year=2023).is_empty()
        assert not SearchFilters(incident_type="Medication Error").is_empty()

    def test_to_qdrant_filter_returns_none_when_empty(self):
        assert SearchFilters().to_qdrant_filter() is None

    def test_to_qdrant_filter_severity(self):
        f = SearchFilters(severity="High")
        result = f.to_qdrant_filter()
        assert result is not None
        # Filter has exactly one must condition
        assert len(result.must) == 1
        cond = result.must[0]
        assert cond.key == "severity"

    def test_to_qdrant_filter_incident_type_uses_match_any(self):
        """Array-contains for incident_type must use MatchAny, not MatchValue."""
        from qdrant_client.models import MatchAny

        f = SearchFilters(incident_type="Airway")
        result = f.to_qdrant_filter()
        assert result is not None
        cond = result.must[0]
        assert cond.key == "incident_type"
        assert isinstance(cond.match, MatchAny)
        assert "Airway" in cond.match.any

    def test_to_qdrant_filter_multi_field(self):
        f = SearchFilters(severity="Critical", year=2022, surgery_type="Ortho")
        result = f.to_qdrant_filter()
        assert result is not None
        assert len(result.must) == 3
        keys = {c.key for c in result.must}
        assert keys == {"severity", "year", "surgery_type"}


# ---------------------------------------------------------------------------
# _rank helper
# ---------------------------------------------------------------------------


class TestRankHelper:
    def _make_sr(self, iid: str, score: float) -> SearchResult:
        return SearchResult(incident_id=iid, score=score, metadata={})

    def test_assigns_1based_ranks(self):
        raw = [self._make_sr("a", 0.9), self._make_sr("b", 0.7), self._make_sr("c", 0.5)]
        ranked = _rank(raw)
        assert [r.rank for r in ranked] == [1, 2, 3]

    def test_preserves_score_and_id(self):
        raw = [self._make_sr("xyz", 0.83)]
        ranked = _rank(raw)
        assert ranked[0].incident_id == "xyz"
        assert ranked[0].score == pytest.approx(0.83)

    def test_empty_input(self):
        assert _rank([]) == []


# ---------------------------------------------------------------------------
# _apply_python_filter
# ---------------------------------------------------------------------------


class TestApplyPythonFilter:
    def _sr(self, **payload) -> SearchResult:
        return SearchResult(incident_id="id", score=0.5, metadata=payload)

    def test_filters_by_severity(self):
        results = [
            self._sr(severity="High"),
            self._sr(severity="Low"),
        ]
        out = _apply_python_filter(results, SearchFilters(severity="High"))
        assert len(out) == 1
        assert out[0].metadata["severity"] == "High"

    def test_filters_by_surgery_type(self):
        results = [
            self._sr(surgery_type="Cardiac"),
            self._sr(surgery_type="Ortho"),
        ]
        out = _apply_python_filter(results, SearchFilters(surgery_type="Cardiac"))
        assert len(out) == 1

    def test_filters_by_year(self):
        results = [self._sr(year=2022), self._sr(year=2023)]
        out = _apply_python_filter(results, SearchFilters(year=2022))
        assert len(out) == 1

    def test_filters_incident_type_array_contains(self):
        results = [
            self._sr(incident_type=["Airway", "Medication"]),
            self._sr(incident_type=["Equipment"]),
        ]
        out = _apply_python_filter(results, SearchFilters(incident_type="Airway"))
        assert len(out) == 1

    def test_no_match_returns_empty(self):
        results = [self._sr(severity="Low")]
        out = _apply_python_filter(results, SearchFilters(severity="Critical"))
        assert out == []

    def test_all_pass_when_filters_match_all(self):
        results = [self._sr(severity="High"), self._sr(severity="High")]
        out = _apply_python_filter(results, SearchFilters(severity="High"))
        assert len(out) == 2


# ---------------------------------------------------------------------------
# SimilaritySearchResult properties
# ---------------------------------------------------------------------------


class TestSimilaritySearchResultProperties:
    def test_defaults_when_metadata_empty(self):
        r = SimilaritySearchResult(incident_id="x", score=0.5, rank=1)
        assert r.severity == "Unknown"
        assert r.incident_type == []
        assert r.root_cause == ""
        assert r.key_learning == ""
        assert r.surgery_type == "Unknown"
        assert r.source == "unknown"

    def test_reads_from_metadata(self):
        meta = {
            "severity": "Critical",
            "incident_type": ["Airway"],
            "root_cause": "Communication failure",
            "key_learning": "Pre-op checklist",
            "surgery_type": "Cardiac",
            "source": "AIR",
        }
        r = SimilaritySearchResult(incident_id="x", score=0.9, rank=1, metadata=meta)
        assert r.severity == "Critical"
        assert r.incident_type == ["Airway"]
        assert r.root_cause == "Communication failure"
        assert r.key_learning == "Pre-op checklist"
        assert r.surgery_type == "Cardiac"
        assert r.source == "AIR"


# ---------------------------------------------------------------------------
# SimilaritySearchEngine (using mocks for dependencies)
# ---------------------------------------------------------------------------


class TestSimilaritySearchEngine:
    def _engine(self, search_results: list[SearchResult]) -> SimilaritySearchEngine:
        """Build a SimilaritySearchEngine with mocked dependencies."""
        embed = MagicMock()
        embed.embed_text.return_value = [0.1] * 4
        embed.embed_incident.return_value = MagicMock(vector=[0.2] * 4)

        store = MagicMock()
        store.search_with_filter.return_value = search_results
        store.search_similar_to_stored.return_value = search_results

        return SimilaritySearchEngine(embed, store)

    def _make_result(self, iid: str, score: float, **meta) -> SearchResult:
        return SearchResult(incident_id=iid, score=score, metadata=meta)

    def test_search_by_text_returns_ranked(self):
        raw = [self._make_result("a", 0.9), self._make_result("b", 0.6)]
        engine = self._engine(raw)
        results = engine.search_by_text("airway event", top_k=2)
        assert len(results) == 2
        assert results[0].rank == 1
        assert results[1].rank == 2

    def test_search_by_text_passes_filter_to_qdrant(self):
        engine = self._engine([])
        f = SearchFilters(severity="High")
        engine.search_by_text("test", filters=f)
        engine._store.search_with_filter.assert_called_once()
        _, kwargs = engine._store.search_with_filter.call_args
        assert kwargs["qdrant_filter"] is not None

    def test_search_by_text_no_filter_when_none(self):
        engine = self._engine([])
        engine.search_by_text("test")
        _, kwargs = engine._store.search_with_filter.call_args
        assert kwargs["qdrant_filter"] is None

    def test_search_by_incident_calls_embed_incident(self):
        incident = MagicMock()
        incident.incident_id = "test-id"
        engine = self._engine([])
        engine.search_by_incident(incident)
        engine._embed.embed_incident.assert_called_once_with(incident, None)

    def test_search_by_vector_delegates_to_store(self):
        raw = [self._make_result("c", 0.75)]
        engine = self._engine(raw)
        results = engine.search_by_vector([0.5] * 4, top_k=3)
        assert results[0].incident_id == "c"
        assert results[0].score == pytest.approx(0.75)
        assert results[0].rank == 1

    def test_search_similar_to_stored_applies_python_filter(self):
        raw = [
            self._make_result("a", 0.9, severity="High"),
            self._make_result("b", 0.8, severity="Low"),
        ]
        engine = self._engine(raw)
        results = engine.search_similar_to_stored(
            "00000000-0000-0000-0000-000000000001",
            filters=SearchFilters(severity="High"),
        )
        assert len(results) == 1
        assert results[0].severity == "High"

    def test_search_by_text_empty_results(self):
        engine = self._engine([])
        results = engine.search_by_text("nothing")
        assert results == []
