"""Evidence tracking and attribution for grounded RAG retrieval.

Wraps retrieval results with structured grounding metadata:
- Grades each result as High / Moderate / Low relevance by score
- Computes query-keyword coverage across retrieved incident metadata
- Derives overall retrieval confidence from grade distribution + coverage
- Formats citeable, attributed context strings ready for LLM injection

All operations are deterministic (no LLM calls).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Relevance grade thresholds (applied to best available score 0-1)
_HIGH_THRESHOLD: float = 0.75
_MODERATE_THRESHOLD: float = 0.50

# Coverage fractions required for each confidence level
_HIGH_COVERAGE: float = 0.60
_MODERATE_COVERAGE: float = 0.30


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class EvidenceItem:
    """One piece of grounded evidence from the retrieved result set.

    Attributes:
        incident_id: Qdrant point ID for this incident.
        similarity_score: Cosine similarity from vector search (0-1).
        rerank_score: Cross-encoder rerank score; None when reranking was
            not applied.
        metadata: VectorMetadata dict (severity, incident_type, root_cause,
            surgery_type, key_learning, etc.).
        relevance_grade: "High", "Moderate", or "Low" based on best score.
        supporting_fields: Metadata keys that contain meaningful content
            (used to explain what makes this evidence useful).
        citation: Human-readable citation string for inline attribution.
    """

    incident_id: str
    similarity_score: float
    rerank_score: float | None
    metadata: dict[str, Any]
    relevance_grade: str
    supporting_fields: list[str]
    citation: str

    @property
    def best_score(self) -> float:
        """Rerank score when available, else similarity score."""
        return self.rerank_score if self.rerank_score is not None else self.similarity_score


@dataclass
class EvidenceBundle:
    """Full evidence package produced by one EvidenceTracker.build_bundle() call.

    Attributes:
        query: Original query string.
        items: Evidence items in descending relevance order.
        total_retrieved: Number of results processed.
        high_relevance_count: Items graded "High".
        moderate_relevance_count: Items graded "Moderate".
        coverage_score: Fraction of query keywords found anywhere in the
            retrieved metadata (0.0 = no overlap, 1.0 = full coverage).
        confidence: "High", "Moderate", "Low", or "Insufficient".
        citations: Formatted citation string for every evidence item.
    """

    query: str
    items: list[EvidenceItem]
    total_retrieved: int
    high_relevance_count: int
    moderate_relevance_count: int
    coverage_score: float
    confidence: str
    citations: list[str] = field(default_factory=list)

    @property
    def is_sufficient(self) -> bool:
        """True when confidence is High or Moderate."""
        return self.confidence in ("High", "Moderate")

    @property
    def supported_count(self) -> int:
        """Number of High + Moderate relevance items."""
        return self.high_relevance_count + self.moderate_relevance_count


# ---------------------------------------------------------------------------
# Evidence tracker
# ---------------------------------------------------------------------------


class EvidenceTracker:
    """Build structured evidence bundles from retrieval results.

    Operates on any object exposing ``incident_id``, ``metadata``, and a
    score attribute (``rerank_score`` for RerankResult, ``score`` for
    SimilaritySearchResult).

    Args:
        high_threshold: Minimum score for a "High" relevance grade.
        moderate_threshold: Minimum score for a "Moderate" relevance grade.
    """

    def __init__(
        self,
        high_threshold: float = _HIGH_THRESHOLD,
        moderate_threshold: float = _MODERATE_THRESHOLD,
    ) -> None:
        self._high = high_threshold
        self._moderate = moderate_threshold

    def build_bundle(
        self,
        query: str,
        results: list[Any],
        keywords: list[str] | None = None,
    ) -> EvidenceBundle:
        """Build an EvidenceBundle from a retrieval result list.

        Args:
            query: Original query string (stored on the bundle).
            results: List of SimilaritySearchResult or RerankResult objects.
            keywords: Query keywords for coverage measurement.
                Pass an empty list or None to skip coverage calculation.

        Returns:
            EvidenceBundle with graded items, coverage score, and confidence.
        """
        kw = keywords or []
        items = [self._make_item(r) for r in results]

        high_count = sum(1 for i in items if i.relevance_grade == "High")
        mod_count = sum(1 for i in items if i.relevance_grade == "Moderate")
        coverage = self._compute_coverage(items, kw)
        confidence = self._derive_confidence(high_count, mod_count, coverage, len(items))
        citations = [i.citation for i in items]

        bundle = EvidenceBundle(
            query=query,
            items=items,
            total_retrieved=len(items),
            high_relevance_count=high_count,
            moderate_relevance_count=mod_count,
            coverage_score=round(coverage, 3),
            confidence=confidence,
            citations=citations,
        )
        logger.debug(
            "Evidence bundle: %d items, confidence=%s, coverage=%.2f, high=%d",
            len(items),
            confidence,
            coverage,
            high_count,
        )
        return bundle

    def format_grounded_context(
        self,
        bundle: EvidenceBundle,
        query: str = "",
    ) -> str:
        """Format evidence as an LLM-injectable grounded context block.

        Unlike RAGRetriever.format_context(), this version adds explicit
        evidence grading, confidence summary, citation markers, and matched
        fields so downstream LLMs can quantify how well-supported the
        retrieved context is.

        Args:
            bundle: Evidence bundle to format.
            query: Original query string (used as a header when non-empty).

        Returns:
            Multi-line plain-text string ready for LLM prompt injection.
        """
        if not bundle.items:
            return "No supporting evidence found."

        lines: list[str] = []

        if query:
            lines.append(f"Query: {query}")
            lines.append("")

        lines += [
            f"Evidence confidence: {bundle.confidence}  "
            f"(coverage: {bundle.coverage_score:.0%}, "
            f"high-relevance: {bundle.high_relevance_count}/{bundle.total_retrieved})",
            "",
            f"Grounded evidence from {bundle.total_retrieved} retrieved incident(s):",
            "",
        ]

        for idx, item in enumerate(bundle.items, start=1):
            meta = item.metadata
            short_id = item.incident_id[:8] + "..."
            lines.append(
                f"[{idx}] Incident {short_id}  "
                f"[{item.relevance_grade} relevance -- score {item.best_score:.3f}]"
            )

            if types := meta.get("incident_type"):
                if isinstance(types, list):
                    lines.append(f"    Types: {', '.join(str(t) for t in types)}")
                else:
                    lines.append(f"    Type: {types}")

            if sev := meta.get("severity"):
                lines.append(f"    Severity: {sev}")

            if surgery := meta.get("surgery_type"):
                lines.append(f"    Surgical context: {surgery}")

            if rc := meta.get("root_cause"):
                lines.append(f"    Root cause: {rc}")

            if kl := meta.get("key_learning"):
                lines.append(f"    Key learning: {kl}")

            if item.supporting_fields:
                lines.append(f"    Matched fields: {', '.join(item.supporting_fields)}")

            lines.append(f"    Citation: {item.citation}")
            lines.append("")

        return "\n".join(lines).rstrip()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _make_item(self, result: Any) -> EvidenceItem:
        """Create an EvidenceItem from any search result object."""
        incident_id: str = str(result.incident_id)
        meta: dict[str, Any] = result.metadata if hasattr(result, "metadata") else {}

        sim_score = float(getattr(result, "score", 0.0))
        rerank_score: float | None = (
            float(result.rerank_score) if hasattr(result, "rerank_score") else None
        )

        effective_score = rerank_score if rerank_score is not None else sim_score
        grade = self._grade_relevance(effective_score)
        citation = self._build_citation(incident_id, meta, effective_score)
        supporting = self._find_supporting_fields(meta)

        return EvidenceItem(
            incident_id=incident_id,
            similarity_score=sim_score,
            rerank_score=rerank_score,
            metadata=meta,
            relevance_grade=grade,
            supporting_fields=supporting,
            citation=citation,
        )

    def _grade_relevance(self, score: float) -> str:
        if score >= self._high:
            return "High"
        if score >= self._moderate:
            return "Moderate"
        return "Low"

    def _build_citation(
        self,
        incident_id: str,
        meta: dict[str, Any],
        score: float,
    ) -> str:
        parts: list[str] = [f"Incident {incident_id[:12]}"]
        if sev := meta.get("severity"):
            parts.append(f"severity={sev}")
        types = meta.get("incident_type")
        if isinstance(types, list) and types:
            parts.append(f"type={types[0]}")
        elif isinstance(types, str) and types:
            parts.append(f"type={types}")
        parts.append(f"score={score:.3f}")
        return " | ".join(parts)

    @staticmethod
    def _find_supporting_fields(meta: dict[str, Any]) -> list[str]:
        """List metadata keys that contain meaningful non-empty content."""
        interesting = [
            "incident_type", "severity", "root_cause", "surgery_type", "key_learning",
        ]
        return [
            k for k in interesting
            if meta.get(k) and meta[k] not in ("Unknown", [], "")
        ]

    def _compute_coverage(
        self,
        items: list[EvidenceItem],
        keywords: list[str],
    ) -> float:
        """Fraction of query keywords found anywhere in the retrieved metadata."""
        if not keywords:
            return 1.0 if items else 0.0

        # Build a single lowercased text blob from all metadata text fields
        text_parts: list[str] = []
        for item in items:
            m = item.metadata
            types = m.get("incident_type", [])
            if isinstance(types, list):
                text_parts.extend(str(t).lower() for t in types)
            elif types:
                text_parts.append(str(types).lower())
            for field in ("root_cause", "severity", "surgery_type", "key_learning"):
                val = m.get(field, "")
                if val:
                    text_parts.append(str(val).lower())

        combined = " ".join(text_parts)
        found = sum(1 for kw in keywords if kw.lower() in combined)
        return found / len(keywords)

    def _derive_confidence(
        self,
        high_count: int,
        moderate_count: int,
        coverage: float,
        total: int,
    ) -> str:
        """Map grade distribution + coverage to a confidence label."""
        if total == 0:
            return "Insufficient"
        if high_count >= 2 and coverage >= _HIGH_COVERAGE:
            return "High"
        if (high_count + moderate_count) >= 2 and coverage >= _MODERATE_COVERAGE:
            return "Moderate"
        if high_count >= 1 or (moderate_count >= 1 and coverage > 0.0):
            return "Low"
        return "Insufficient"
