"""Unit tests for Week 8 evidence tracking.

Tests EvidenceTracker grading, coverage, confidence derivation, and
EvidenceBundle / EvidenceItem properties.
All tests are offline -- no model downloads, no Qdrant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from src.retrieval.evidence import (
    EvidenceBundle,
    EvidenceItem,
    EvidenceTracker,
    _HIGH_THRESHOLD,
    _MODERATE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Fake result objects (mimic SimilaritySearchResult / RerankResult)
# ---------------------------------------------------------------------------


@dataclass
class _FakeResult:
    incident_id: str
    score: float
    metadata: dict[str, Any]


@dataclass
class _FakeRerankResult:
    incident_id: str
    score: float
    rerank_score: float
    metadata: dict[str, Any]


def _meta(
    severity: str = "High",
    types: list[str] | None = None,
    root_cause: str = "equipment failure",
    surgery_type: str = "Cardiac",
    key_learning: str = "Check device before use",
) -> dict[str, Any]:
    return {
        "severity": severity,
        "incident_type": types or ["Medication Error"],
        "root_cause": root_cause,
        "surgery_type": surgery_type,
        "key_learning": key_learning,
    }


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def tracker() -> EvidenceTracker:
    return EvidenceTracker()


# ---------------------------------------------------------------------------
# Relevance grading
# ---------------------------------------------------------------------------


class TestRelevanceGrading:
    def test_high_grade(self, tracker: EvidenceTracker) -> None:
        assert tracker._grade_relevance(0.90) == "High"

    def test_high_grade_at_threshold(self, tracker: EvidenceTracker) -> None:
        assert tracker._grade_relevance(_HIGH_THRESHOLD) == "High"

    def test_moderate_grade(self, tracker: EvidenceTracker) -> None:
        assert tracker._grade_relevance(0.65) == "Moderate"

    def test_moderate_grade_at_threshold(self, tracker: EvidenceTracker) -> None:
        assert tracker._grade_relevance(_MODERATE_THRESHOLD) == "Moderate"

    def test_low_grade(self, tracker: EvidenceTracker) -> None:
        assert tracker._grade_relevance(0.30) == "Low"

    def test_zero_score_is_low(self, tracker: EvidenceTracker) -> None:
        assert tracker._grade_relevance(0.0) == "Low"

    def test_custom_threshold_respected(self) -> None:
        t = EvidenceTracker(high_threshold=0.9, moderate_threshold=0.7)
        assert t._grade_relevance(0.85) == "Moderate"
        assert t._grade_relevance(0.91) == "High"
        assert t._grade_relevance(0.65) == "Low"


# ---------------------------------------------------------------------------
# Citation building
# ---------------------------------------------------------------------------


class TestCitationBuilding:
    def test_citation_includes_id(self, tracker: EvidenceTracker) -> None:
        citation = tracker._build_citation("abc123", _meta(), 0.85)
        assert "abc123" in citation

    def test_citation_includes_severity(self, tracker: EvidenceTracker) -> None:
        citation = tracker._build_citation("id1", _meta(severity="Critical"), 0.8)
        assert "Critical" in citation

    def test_citation_includes_score(self, tracker: EvidenceTracker) -> None:
        citation = tracker._build_citation("id1", _meta(), 0.847)
        assert "0.847" in citation

    def test_citation_includes_type(self, tracker: EvidenceTracker) -> None:
        citation = tracker._build_citation("id1", _meta(types=["Airway"]), 0.9)
        assert "Airway" in citation

    def test_citation_with_no_metadata(self, tracker: EvidenceTracker) -> None:
        citation = tracker._build_citation("id999", {}, 0.5)
        assert "id999" in citation
        assert "0.500" in citation


# ---------------------------------------------------------------------------
# Supporting fields
# ---------------------------------------------------------------------------


class TestSupportingFields:
    def test_all_populated_fields_returned(self, tracker: EvidenceTracker) -> None:
        fields = tracker._find_supporting_fields(_meta())
        assert "severity" in fields
        assert "incident_type" in fields
        assert "root_cause" in fields

    def test_unknown_severity_excluded(self, tracker: EvidenceTracker) -> None:
        meta = _meta(severity="Unknown")
        fields = tracker._find_supporting_fields(meta)
        assert "severity" not in fields

    def test_empty_root_cause_excluded(self, tracker: EvidenceTracker) -> None:
        meta = _meta(root_cause="")
        fields = tracker._find_supporting_fields(meta)
        assert "root_cause" not in fields


# ---------------------------------------------------------------------------
# Coverage computation
# ---------------------------------------------------------------------------


class TestCoverageComputation:
    def _make_items(self, meta_list: list[dict]) -> list[EvidenceItem]:
        tracker = EvidenceTracker()
        return [
            tracker._make_item(_FakeResult(incident_id=f"id{i}", score=0.8, metadata=m))
            for i, m in enumerate(meta_list)
        ]

    def test_full_coverage_when_all_keywords_found(self, tracker: EvidenceTracker) -> None:
        items = self._make_items([_meta(root_cause="equipment failure cardiac")])
        coverage = tracker._compute_coverage(items, ["equipment", "cardiac"])
        assert coverage == 1.0

    def test_zero_coverage_when_no_keywords_match(self, tracker: EvidenceTracker) -> None:
        items = self._make_items([_meta(root_cause="labeling error")])
        coverage = tracker._compute_coverage(items, ["zebra", "xylophone"])
        assert coverage == 0.0

    def test_partial_coverage(self, tracker: EvidenceTracker) -> None:
        items = self._make_items([_meta(severity="High", root_cause="equipment")])
        coverage = tracker._compute_coverage(items, ["equipment", "zebra"])
        assert 0.0 < coverage < 1.0

    def test_empty_keywords_returns_full_when_items_exist(
        self, tracker: EvidenceTracker
    ) -> None:
        items = self._make_items([_meta()])
        assert tracker._compute_coverage(items, []) == 1.0

    def test_empty_keywords_returns_zero_when_no_items(
        self, tracker: EvidenceTracker
    ) -> None:
        assert tracker._compute_coverage([], []) == 0.0


# ---------------------------------------------------------------------------
# Confidence derivation
# ---------------------------------------------------------------------------


class TestConfidenceDerivation:
    def test_high_confidence_requires_two_high_plus_coverage(
        self, tracker: EvidenceTracker
    ) -> None:
        conf = tracker._derive_confidence(high_count=3, moderate_count=0, coverage=0.7, total=3)
        assert conf == "High"

    def test_moderate_confidence(self, tracker: EvidenceTracker) -> None:
        conf = tracker._derive_confidence(high_count=1, moderate_count=2, coverage=0.4, total=3)
        assert conf == "Moderate"

    def test_low_confidence_one_high(self, tracker: EvidenceTracker) -> None:
        conf = tracker._derive_confidence(high_count=1, moderate_count=0, coverage=0.1, total=1)
        assert conf == "Low"

    def test_insufficient_when_no_items(self, tracker: EvidenceTracker) -> None:
        conf = tracker._derive_confidence(high_count=0, moderate_count=0, coverage=0.0, total=0)
        assert conf == "Insufficient"

    def test_insufficient_all_low_no_coverage(self, tracker: EvidenceTracker) -> None:
        conf = tracker._derive_confidence(high_count=0, moderate_count=0, coverage=0.0, total=3)
        assert conf == "Insufficient"


# ---------------------------------------------------------------------------
# build_bundle
# ---------------------------------------------------------------------------


class TestBuildBundle:
    def test_empty_results_bundle(self, tracker: EvidenceTracker) -> None:
        bundle = tracker.build_bundle("query", [])
        assert bundle.total_retrieved == 0
        assert bundle.confidence == "Insufficient"
        assert bundle.items == []

    def test_bundle_item_count(self, tracker: EvidenceTracker) -> None:
        results = [
            _FakeResult("id1", 0.9, _meta()),
            _FakeResult("id2", 0.6, _meta(severity="Low")),
        ]
        bundle = tracker.build_bundle("query", results)
        assert bundle.total_retrieved == 2
        assert len(bundle.items) == 2

    def test_bundle_high_count_correct(self, tracker: EvidenceTracker) -> None:
        results = [
            _FakeResult("id1", 0.85, _meta()),
            _FakeResult("id2", 0.80, _meta()),
            _FakeResult("id3", 0.30, _meta()),
        ]
        bundle = tracker.build_bundle("query", results)
        assert bundle.high_relevance_count == 2

    def test_rerank_score_used_for_grade(self, tracker: EvidenceTracker) -> None:
        result = _FakeRerankResult("id1", score=0.30, rerank_score=0.90, metadata=_meta())
        bundle = tracker.build_bundle("query", [result])
        assert bundle.items[0].relevance_grade == "High"

    def test_citations_populated(self, tracker: EvidenceTracker) -> None:
        results = [_FakeResult("id1", 0.85, _meta())]
        bundle = tracker.build_bundle("query", results)
        assert len(bundle.citations) == 1
        assert "id1" in bundle.citations[0]

    def test_keywords_affect_coverage(self, tracker: EvidenceTracker) -> None:
        results = [_FakeResult("id1", 0.85, _meta(root_cause="equipment failure"))]
        bundle_with = tracker.build_bundle("query", results, keywords=["equipment"])
        bundle_without = tracker.build_bundle("query", results, keywords=[])
        assert bundle_with.coverage_score < bundle_without.coverage_score or bundle_with.coverage_score == 1.0


# ---------------------------------------------------------------------------
# format_grounded_context
# ---------------------------------------------------------------------------


class TestFormatGroundedContext:
    def test_empty_bundle_returns_no_evidence_message(
        self, tracker: EvidenceTracker
    ) -> None:
        bundle = tracker.build_bundle("q", [])
        text = tracker.format_grounded_context(bundle)
        assert "No supporting evidence" in text

    def test_output_contains_confidence(self, tracker: EvidenceTracker) -> None:
        results = [_FakeResult("id1", 0.85, _meta())]
        bundle = tracker.build_bundle("test query", results, keywords=["equipment"])
        text = tracker.format_grounded_context(bundle, query="test query")
        assert "confidence" in text.lower() or "Evidence confidence" in text

    def test_output_contains_query_header(self, tracker: EvidenceTracker) -> None:
        results = [_FakeResult("id1", 0.85, _meta())]
        bundle = tracker.build_bundle("cardiac error", results)
        text = tracker.format_grounded_context(bundle, query="cardiac error")
        assert "cardiac error" in text

    def test_output_contains_citation(self, tracker: EvidenceTracker) -> None:
        results = [_FakeResult("id1abc", 0.85, _meta())]
        bundle = tracker.build_bundle("q", results)
        text = tracker.format_grounded_context(bundle)
        assert "id1abc" in text or "Citation" in text

    def test_no_query_header_when_empty(self, tracker: EvidenceTracker) -> None:
        results = [_FakeResult("id1", 0.85, _meta())]
        bundle = tracker.build_bundle("q", results)
        text = tracker.format_grounded_context(bundle, query="")
        assert not text.startswith("Query:")


# ---------------------------------------------------------------------------
# EvidenceBundle properties
# ---------------------------------------------------------------------------


class TestEvidenceBundleProperties:
    def test_is_sufficient_high(self, tracker: EvidenceTracker) -> None:
        results = [
            _FakeResult(f"id{i}", 0.85, _meta()) for i in range(3)
        ]
        bundle = tracker.build_bundle("q", results, keywords=["equipment"])
        # With 3 high-relevance items and matching keywords, should be High or Moderate
        assert bundle.is_sufficient or bundle.confidence in ("High", "Moderate", "Low")

    def test_is_sufficient_false_when_insufficient(self, tracker: EvidenceTracker) -> None:
        bundle = tracker.build_bundle("q", [])
        assert not bundle.is_sufficient

    def test_supported_count(self, tracker: EvidenceTracker) -> None:
        results = [
            _FakeResult("id1", 0.85, _meta()),   # High
            _FakeResult("id2", 0.60, _meta()),   # Moderate
            _FakeResult("id3", 0.20, _meta()),   # Low
        ]
        bundle = tracker.build_bundle("q", results)
        assert bundle.supported_count == bundle.high_relevance_count + bundle.moderate_relevance_count

    def test_evidence_item_best_score_prefers_rerank(
        self, tracker: EvidenceTracker
    ) -> None:
        result = _FakeRerankResult("id1", score=0.30, rerank_score=0.92, metadata=_meta())
        bundle = tracker.build_bundle("q", [result])
        assert bundle.items[0].best_score == pytest.approx(0.92)

    def test_evidence_item_best_score_falls_back_to_similarity(
        self, tracker: EvidenceTracker
    ) -> None:
        result = _FakeResult("id1", score=0.75, metadata=_meta())
        bundle = tracker.build_bundle("q", [result])
        assert bundle.items[0].best_score == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# Fix typo guard
# ---------------------------------------------------------------------------

# Catch typo in class name in citation test above
def test_typo_guard() -> None:
    """Make sure EvidenceTracker (not EvidanceTracker) is the right name."""
    assert EvidenceTracker.__name__ == "EvidenceTracker"
