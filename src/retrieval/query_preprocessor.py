"""Query preprocessing for clinical incident retrieval.

Transforms raw user queries into structured objects that guide retrieval:
- Intent classification (keyword-based, deterministic -- no LLM required)
- Clinical keyword extraction with stopword filtering
- SearchFilters inference from query text (severity, year)
- Query expansion with clinical synonyms

All operations are deterministic and offline; no model downloads required.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.retrieval.similarity_search import SearchFilters
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Stopwords stripped before keyword extraction
_STOPWORDS: frozenset[str] = frozenset({
    "a", "an", "the", "and", "or", "in", "of", "to", "for", "with",
    "is", "are", "was", "were", "be", "been", "being", "have", "has",
    "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "this", "that", "these", "those", "from", "by",
    "at", "on", "as", "if", "then", "than", "what", "which", "who",
    "how", "all", "any", "both", "each", "few", "more", "most",
    "other", "some", "such", "not", "only", "same", "so", "out",
    "up", "about", "after", "before", "during", "show", "find",
    "get", "give", "tell", "can", "please", "me", "we", "our",
    "you", "your", "it", "its", "i", "my",
})

# Intent name -> trigger substrings (first match across priority order wins)
_INTENT_KEYWORDS: dict[str, list[str]] = {
    "root_cause": [
        "cause", "why", "reason", "contributing", "root cause", "led to",
        "resulted in", "trigger", "because", "due to", "arising",
    ],
    "pattern_analysis": [
        "pattern", "trend", "common", "recurring", "frequency", "how often",
        "multiple", "repeated", "cluster", "group", "aggregate",
    ],
    "safety_recommendations": [
        "prevent", "recommendation", "avoid", "reduce", "improve", "mitigate",
        "protocol", "guideline", "safety", "lesson",
    ],
    "similar_incidents": [
        "similar", "like", "same", "comparable", "related", "alike",
        "equivalent", "resembl", "match",
    ],
}

# Query word -> severity enum value for filter inference
_SEVERITY_MAP: dict[str, str] = {
    "critical": "Critical",
    "severe": "High",
    "high": "High",
    "moderate": "Moderate",
    "medium": "Moderate",
    "low": "Low",
    "minor": "Low",
}

# Clinical base term -> synonyms for query expansion
_CLINICAL_SYNONYMS: dict[str, list[str]] = {
    "anesthesia": ["anaesthesia", "anesthetic", "anaesthetic"],
    "medication": ["drug", "medicine", "pharmaceutical"],
    "intubation": ["intubate", "airway", "endotracheal"],
    "surgery": ["operation", "procedure", "operative", "surgical"],
    "monitor": ["monitoring", "surveillance"],
    "error": ["mistake", "failure", "incident", "adverse event"],
    "cardiac": ["heart", "cardiovascular"],
    "respiratory": ["breathing", "pulmonary", "ventilation"],
    "equipment": ["device", "instrument", "machine", "apparatus"],
    "nurse": ["nursing", "clinical staff", "healthcare provider"],
    "patient": ["subject", "individual", "case"],
}

_YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


class QueryIntent(str, Enum):
    """Detected retrieval intent of a clinical query."""

    SIMILAR_INCIDENTS = "similar_incidents"
    ROOT_CAUSE = "root_cause"
    PATTERN_ANALYSIS = "pattern_analysis"
    SAFETY_RECOMMENDATIONS = "safety_recommendations"
    GENERAL = "general"


@dataclass
class ProcessedQuery:
    """Structured representation of a preprocessed clinical query.

    Attributes:
        original: Raw query string as provided by the caller.
        cleaned: Lowercased, stripped version used for analysis.
        intent: Detected retrieval intent.
        keywords: Clinical content words extracted from the query.
        expanded_terms: Additional synonyms introduced by query expansion.
        suggested_filters: SearchFilters inferred from query text.
            None when no structured constraints were detected.
    """

    original: str
    cleaned: str
    intent: QueryIntent
    keywords: list[str] = field(default_factory=list)
    expanded_terms: list[str] = field(default_factory=list)
    suggested_filters: SearchFilters | None = None

    @property
    def all_terms(self) -> list[str]:
        """Unique union of keywords and expanded terms (keywords first)."""
        seen: set[str] = set()
        result: list[str] = []
        for term in self.keywords + self.expanded_terms:
            if term not in seen:
                seen.add(term)
                result.append(term)
        return result


# ---------------------------------------------------------------------------
# Preprocessor
# ---------------------------------------------------------------------------


class QueryPreprocessor:
    """Transform raw clinical queries into structured retrieval parameters.

    All processing is deterministic and keyword-based; no model downloads are
    required.  Custom intent tables and synonym maps can be injected for
    testing or domain-specific tuning.

    Args:
        intent_keywords: intent_name -> trigger substrings.
            Defaults to the built-in clinical intent map.
        clinical_synonyms: base_term -> synonyms for expansion.
            Defaults to the built-in clinical synonym table.
        severity_map: query_word -> severity enum value for filter inference.
    """

    def __init__(
        self,
        intent_keywords: dict[str, list[str]] | None = None,
        clinical_synonyms: dict[str, list[str]] | None = None,
        severity_map: dict[str, str] | None = None,
    ) -> None:
        self._intent_kw = intent_keywords if intent_keywords is not None else _INTENT_KEYWORDS
        self._synonyms = clinical_synonyms if clinical_synonyms is not None else _CLINICAL_SYNONYMS
        self._severity_map = severity_map if severity_map is not None else _SEVERITY_MAP

    def preprocess(self, query: str) -> ProcessedQuery:
        """Run the full preprocessing pipeline on a clinical query.

        Args:
            query: Raw free-text clinical query string.

        Returns:
            ProcessedQuery with intent, keywords, expansions, and inferred
            filters.
        """
        cleaned = query.strip().lower()
        intent = self._classify_intent(cleaned)
        keywords = self._extract_keywords(cleaned)
        expanded = self._expand_terms(keywords)
        filters = self._infer_filters(cleaned)

        logger.debug(
            "Preprocessed query: intent=%s keywords=%r filters=%s",
            intent.value,
            keywords[:5],
            filters,
        )

        return ProcessedQuery(
            original=query,
            cleaned=cleaned,
            intent=intent,
            keywords=keywords,
            expanded_terms=expanded,
            suggested_filters=filters,
        )

    # ------------------------------------------------------------------
    # Pipeline steps
    # ------------------------------------------------------------------

    def _classify_intent(self, cleaned: str) -> QueryIntent:
        """Keyword-based intent detection; first match in priority order wins."""
        priority = [
            QueryIntent.ROOT_CAUSE,
            QueryIntent.PATTERN_ANALYSIS,
            QueryIntent.SAFETY_RECOMMENDATIONS,
            QueryIntent.SIMILAR_INCIDENTS,
        ]
        for intent in priority:
            triggers = self._intent_kw.get(intent.value, [])
            if any(trigger in cleaned for trigger in triggers):
                return intent
        return QueryIntent.GENERAL

    def _extract_keywords(self, cleaned: str) -> list[str]:
        """Extract content words by stripping punctuation and stopwords."""
        words = [
            w.strip(".,;:()\"'?!")
            for w in cleaned.split()
        ]
        return [
            w for w in words
            if len(w) > 2 and w not in _STOPWORDS and w.isalpha() or
            (len(w) > 2 and w not in _STOPWORDS and not w.replace("-", "").isdigit())
        ]

    def _expand_terms(self, keywords: list[str]) -> list[str]:
        """Add clinical synonyms for each keyword found in the synonym table."""
        expanded: list[str] = []
        keyword_set = set(keywords)
        for kw in keywords:
            for base, synonyms in self._synonyms.items():
                all_forms = [base] + synonyms
                if kw in all_forms:
                    for form in all_forms:
                        if form != kw and form not in keyword_set and form not in expanded:
                            expanded.append(form)
        return expanded

    def _infer_filters(self, cleaned: str) -> SearchFilters | None:
        """Detect severity and year constraints from query text."""
        severity: str | None = None
        year: int | None = None

        words = cleaned.split()
        for word in words:
            w = word.strip(".,;:()")
            if w in self._severity_map:
                severity = self._severity_map[w]
                break

        year_match = _YEAR_PATTERN.search(cleaned)
        if year_match:
            year = int(year_match.group(1))

        if severity is not None or year is not None:
            return SearchFilters(severity=severity, year=year)
        return None
