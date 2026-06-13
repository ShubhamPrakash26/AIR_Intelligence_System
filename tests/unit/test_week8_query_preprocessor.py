"""Unit tests for Week 8 query preprocessing.

Tests QueryPreprocessor intent classification, keyword extraction,
filter inference, query expansion, and the ProcessedQuery dataclass.
All tests are offline -- no model downloads, no Qdrant.
"""

from __future__ import annotations

import pytest

from src.retrieval.query_preprocessor import (
    ProcessedQuery,
    QueryIntent,
    QueryPreprocessor,
)
from src.retrieval.similarity_search import SearchFilters


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def preprocessor() -> QueryPreprocessor:
    return QueryPreprocessor()


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------


class TestIntentClassification:
    def test_root_cause_intent_detected(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("What is the root cause of medication errors?")
        assert pq.intent == QueryIntent.ROOT_CAUSE

    def test_root_cause_via_why(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("why did this incident occur during induction?")
        assert pq.intent == QueryIntent.ROOT_CAUSE

    def test_root_cause_via_contributing(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("contributing factors to airway management failures")
        assert pq.intent == QueryIntent.ROOT_CAUSE

    def test_pattern_analysis_intent(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("show me patterns in cardiac surgery incidents")
        assert pq.intent == QueryIntent.PATTERN_ANALYSIS

    def test_pattern_analysis_via_trend(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("what trends exist in recurring drug errors?")
        assert pq.intent == QueryIntent.PATTERN_ANALYSIS

    def test_pattern_analysis_via_frequency(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("how often do equipment failures happen?")
        assert pq.intent == QueryIntent.PATTERN_ANALYSIS

    def test_safety_recommendations_intent(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("how to prevent medication errors in anaesthesia")
        assert pq.intent == QueryIntent.SAFETY_RECOMMENDATIONS

    def test_safety_recommendations_via_guideline(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("what guidelines exist to improve patient safety?")
        assert pq.intent == QueryIntent.SAFETY_RECOMMENDATIONS

    def test_similar_incidents_intent(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("find similar incidents to syringe labeling errors")
        assert pq.intent == QueryIntent.SIMILAR_INCIDENTS

    def test_similar_incidents_via_comparable(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("show comparable cases with high severity outcomes")
        assert pq.intent == QueryIntent.SIMILAR_INCIDENTS

    def test_general_intent_fallback(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("anaesthesia incidents 2023")
        assert pq.intent == QueryIntent.GENERAL

    def test_root_cause_prioritised_over_pattern(self, preprocessor: QueryPreprocessor) -> None:
        # "cause" should win over "pattern" due to priority ordering
        pq = preprocessor.preprocess("what causes recurring patterns in airway incidents?")
        assert pq.intent == QueryIntent.ROOT_CAUSE


# ---------------------------------------------------------------------------
# Keyword extraction
# ---------------------------------------------------------------------------


class TestKeywordExtraction:
    def test_stopwords_removed(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("the medication error in the operating room")
        assert "the" not in pq.keywords
        assert "in" not in pq.keywords

    def test_content_words_kept(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("cardiac surgery equipment failure")
        assert "cardiac" in pq.keywords
        assert "surgery" in pq.keywords
        assert "equipment" in pq.keywords
        assert "failure" in pq.keywords

    def test_punctuation_stripped(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("syringe labeling: errors, mistakes?")
        # Should not include punctuation-laden forms
        for kw in pq.keywords:
            assert ":" not in kw
            assert "," not in kw
            assert "?" not in kw

    def test_short_words_excluded(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("do we have an error log?")
        assert "do" not in pq.keywords
        assert "we" not in pq.keywords
        assert "an" not in pq.keywords

    def test_empty_query_returns_empty_keywords(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("")
        assert pq.keywords == []


# ---------------------------------------------------------------------------
# Filter inference
# ---------------------------------------------------------------------------


class TestFilterInference:
    def test_critical_severity_inferred(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("show all critical incidents from last year")
        assert pq.suggested_filters is not None
        assert pq.suggested_filters.severity == "Critical"

    def test_high_severity_inferred(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("high severity cardiac events")
        assert pq.suggested_filters is not None
        assert pq.suggested_filters.severity == "High"

    def test_low_severity_inferred(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("low severity medication incidents")
        assert pq.suggested_filters is not None
        assert pq.suggested_filters.severity == "Low"

    def test_year_inferred(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("medication errors reported in 2023")
        assert pq.suggested_filters is not None
        assert pq.suggested_filters.year == 2023

    def test_severity_and_year_combined(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("critical incidents in 2022")
        assert pq.suggested_filters is not None
        assert pq.suggested_filters.severity == "Critical"
        assert pq.suggested_filters.year == 2022

    def test_no_filter_when_none_detected(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("medication errors in anaesthesia")
        assert pq.suggested_filters is None

    def test_moderate_maps_correctly(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("moderate severity drug errors")
        assert pq.suggested_filters is not None
        assert pq.suggested_filters.severity == "Moderate"


# ---------------------------------------------------------------------------
# Query expansion
# ---------------------------------------------------------------------------


class TestQueryExpansion:
    def test_synonyms_added_for_anesthesia(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("anesthesia related incidents")
        assert any("anaesthesia" in t or "anesthetic" in t for t in pq.expanded_terms)

    def test_synonyms_added_for_medication(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("medication administration errors")
        assert len(pq.expanded_terms) > 0

    def test_no_duplicates_in_expanded(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("surgery equipment errors")
        assert len(pq.expanded_terms) == len(set(pq.expanded_terms))

    def test_no_expansion_for_unknown_term(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("xylophone zither")
        assert pq.expanded_terms == []


# ---------------------------------------------------------------------------
# ProcessedQuery dataclass
# ---------------------------------------------------------------------------


class TestProcessedQuery:
    def test_all_terms_is_union(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("anesthesia equipment failure")
        all_t = pq.all_terms
        for kw in pq.keywords:
            assert kw in all_t
        for et in pq.expanded_terms:
            assert et in all_t

    def test_all_terms_no_duplicates(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("anesthesia errors equipment incidents")
        assert len(pq.all_terms) == len(set(pq.all_terms))

    def test_original_preserved(self, preprocessor: QueryPreprocessor) -> None:
        query = "  Critical Medication Errors  "
        pq = preprocessor.preprocess(query)
        assert pq.original == query

    def test_cleaned_is_lowercase_stripped(self, preprocessor: QueryPreprocessor) -> None:
        pq = preprocessor.preprocess("  CRITICAL Medication Errors  ")
        assert pq.cleaned == "critical medication errors"


# ---------------------------------------------------------------------------
# Custom injection
# ---------------------------------------------------------------------------


class TestCustomInjection:
    def test_custom_intent_keywords(self) -> None:
        custom_intents = {"similar_incidents": ["zebra"]}
        pp = QueryPreprocessor(intent_keywords=custom_intents)
        pq = pp.preprocess("find a zebra incident")
        assert pq.intent == QueryIntent.SIMILAR_INCIDENTS

    def test_custom_severity_map(self) -> None:
        custom_sev = {"catastrophic": "Critical"}
        pp = QueryPreprocessor(severity_map=custom_sev)
        pq = pp.preprocess("catastrophic airway events")
        assert pq.suggested_filters is not None
        assert pq.suggested_filters.severity == "Critical"

    def test_custom_synonyms(self) -> None:
        custom_syn = {"robot": ["android", "automaton"]}
        pp = QueryPreprocessor(clinical_synonyms=custom_syn)
        pq = pp.preprocess("robot failures in theatre")
        assert "android" in pq.expanded_terms or "automaton" in pq.expanded_terms
