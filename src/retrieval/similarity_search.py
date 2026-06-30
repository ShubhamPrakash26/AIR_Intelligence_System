"""Semantic similarity search engine for clinical incidents.

Wraps the EmbeddingEngine and QdrantHandler to provide a high-level search
interface.  Supports:
  - Text-query search       (search_by_text)
  - Incident-object search  (search_by_incident)
  - Raw-vector search       (search_by_vector)
  - Stored-point search     (search_similar_to_stored)

All methods return a ranked list of SimilaritySearchResult objects that carry
the Qdrant score, full payload metadata, and the result's rank position so
downstream rerankers can reorder without losing context.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.embeddings.engine import EmbeddingEngine
from src.models.analysis import AIAnalysis
from src.models.incident import Incident
from src.utils.logger import get_logger
from src.vector_store.qdrant_handler import QdrantHandler, SearchResult

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Filter model
# ---------------------------------------------------------------------------


@dataclass
class SearchFilters:
    """Structured filter criteria for incident similarity search.

    All fields are optional.  Only non-None fields are applied.  When
    ``incident_type`` is set, Qdrant checks whether the stored list *contains*
    that value (array-member match), which is different from the scalar
    equality match used for the other fields.

    Attributes:
        severity: Match incidents with this exact severity level
            (``"Low"``, ``"Moderate"``, ``"High"``, ``"Critical"``).
        surgery_type: Match incidents from this surgical specialty.
        year: Match incidents from this calendar year.
        incident_type: Match incidents whose ``incident_type`` list includes
            this category.
    """

    severity: str | None = None
    surgery_type: str | None = None
    year: int | None = None
    incident_type: str | None = None
    source_type: str | None = None

    def is_empty(self) -> bool:
        return all(
            v is None
            for v in (
                self.severity,
                self.surgery_type,
                self.year,
                self.incident_type,
                self.source_type,
            )
        )

    def to_qdrant_filter(self) -> Any | None:
        """Build a ``qdrant_client.models.Filter`` from the active fields.

        Returns ``None`` when no fields are set so callers can short-circuit.
        """
        if self.is_empty():
            return None

        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue

        conditions: list[FieldCondition] = []

        if self.severity is not None:
            conditions.append(
                FieldCondition(key="severity", match=MatchValue(value=self.severity))
            )
        if self.surgery_type is not None:
            conditions.append(
                FieldCondition(key="surgery_type", match=MatchValue(value=self.surgery_type))
            )
        if self.year is not None:
            conditions.append(
                FieldCondition(key="year", match=MatchValue(value=self.year))
            )
        if self.incident_type is not None:
            # Array-contains: stored list must include this value
            conditions.append(
                FieldCondition(
                    key="incident_type",
                    match=MatchAny(any=[self.incident_type]),
                )
            )
        if self.source_type is not None:
            conditions.append(
                FieldCondition(key="source_type", match=MatchValue(value=self.source_type))
            )

        return Filter(must=conditions) if conditions else None


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class SimilaritySearchResult:
    """A single ranked result from the similarity search engine.

    Attributes:
        incident_id: UUID of the retrieved incident.
        score: Cosine similarity score (0–1; higher = more similar).
        rank: 1-based position in the result list (1 = most similar).
        metadata: Full Qdrant payload stored with the vector.
    """

    incident_id: str
    score: float
    rank: int
    metadata: dict[str, Any] = field(default_factory=dict)

    # Convenience accessors --------------------------------------------------

    @property
    def severity(self) -> str:
        return self.metadata.get("severity", "Unknown")

    @property
    def incident_type(self) -> list[str]:
        return self.metadata.get("incident_type", [])

    @property
    def root_cause(self) -> str:
        return self.metadata.get("root_cause", "")

    @property
    def key_learning(self) -> str:
        return self.metadata.get("key_learning", "")

    @property
    def surgery_type(self) -> str:
        return self.metadata.get("surgery_type", "Unknown")

    @property
    def source(self) -> str:
        return self.metadata.get("source", "unknown")


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class SimilaritySearchEngine:
    """High-level semantic search over stored incident vectors.

    Args:
        embedding_engine: EmbeddingEngine instance used to embed query text
            or incident objects before searching.
        qdrant_handler: QdrantHandler connected to the target collection.
    """

    def __init__(
        self,
        embedding_engine: EmbeddingEngine,
        qdrant_handler: QdrantHandler,
    ) -> None:
        self._embed = embedding_engine
        self._store = qdrant_handler

    # ------------------------------------------------------------------
    # Primary search methods
    # ------------------------------------------------------------------

    def search_by_text(
        self,
        query: str,
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> list[SimilaritySearchResult]:
        """Embed an arbitrary text query and return the most similar incidents.

        Useful for querying by clinical concept (e.g. "labeling failure",
        "induction phase airway event") without a specific incident object.

        Args:
            query: Free-text clinical query string.
            top_k: Maximum number of results.
            filters: Optional structured filter to narrow the search space.

        Returns:
            Ranked list of SimilaritySearchResult.
        """
        logger.debug("search_by_text: '%s…' top_k=%d", query[:60], top_k)
        vector = self._embed.embed_text(query)
        return self.search_by_vector(vector, top_k=top_k, filters=filters)

    def search_by_incident(
        self,
        incident: Incident,
        analysis: AIAnalysis | None = None,
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> list[SimilaritySearchResult]:
        """Embed an incident object and return the most similar stored incidents.

        When ``analysis`` is provided the embed text is enriched with root
        cause and key learning fields, producing a more semantically specific
        query vector.

        Args:
            incident: The reference incident to search from.
            analysis: Optional AI analysis for richer embedding.
            top_k: Maximum number of results.
            filters: Optional structured filter.

        Returns:
            Ranked list of SimilaritySearchResult.
        """
        logger.debug(
            "search_by_incident: id=%s top_k=%d", incident.incident_id, top_k
        )
        vector = self._embed.embed_incident(incident, analysis).vector
        return self.search_by_vector(vector, top_k=top_k, filters=filters)

    def search_by_vector(
        self,
        vector: list[float],
        top_k: int = 5,
        filters: SearchFilters | None = None,
    ) -> list[SimilaritySearchResult]:
        """Search directly with a pre-computed vector.

        Args:
            vector: Dense float embedding vector.
            top_k: Maximum number of results.
            filters: Optional structured filter.

        Returns:
            Ranked list of SimilaritySearchResult.
        """
        qdrant_filter = filters.to_qdrant_filter() if filters else None
        raw: list[SearchResult] = self._store.search_with_filter(
            query_vector=vector,
            top_k=top_k,
            qdrant_filter=qdrant_filter,
        )
        return _rank(raw)

    def search_similar_to_stored(
        self,
        incident_id: str,
        top_k: int = 5,
        exclude_self: bool = True,
        filters: SearchFilters | None = None,
    ) -> list[SimilaritySearchResult]:
        """Find incidents similar to a stored one without re-embedding.

        Qdrant serves the stored vector for ``incident_id`` directly, so no
        embedding model call is needed — ideal for "find similar to this case"
        interactions in production.

        Args:
            incident_id: UUID of the reference incident (must be stored).
            top_k: Number of results to return.
            exclude_self: Drop the reference incident from results.
            filters: Optional structured filter.

        Returns:
            Ranked list of SimilaritySearchResult.
        """
        logger.debug(
            "search_similar_to_stored: id=%s top_k=%d", incident_id, top_k
        )
        raw = self._store.search_similar_to_stored(
            incident_id=incident_id,
            top_k=top_k,
            exclude_self=exclude_self,
        )
        # Apply client-side filter when qdrant's search_similar_to_stored
        # doesn't accept a filter parameter (can be added later as needed)
        if filters and not filters.is_empty():
            raw = _apply_python_filter(raw, filters)
        return _rank(raw)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _rank(results: list[SearchResult]) -> list[SimilaritySearchResult]:
    """Convert raw SearchResult list to ranked SimilaritySearchResult list."""
    return [
        SimilaritySearchResult(
            incident_id=r.incident_id,
            score=r.score,
            rank=i + 1,
            metadata=r.metadata,
        )
        for i, r in enumerate(results)
    ]


def _apply_python_filter(
    results: list[SearchResult],
    filters: SearchFilters,
) -> list[SearchResult]:
    """Apply filter conditions in Python when they cannot be passed to Qdrant."""
    out: list[SearchResult] = []
    for r in results:
        payload = r.metadata
        if filters.severity and payload.get("severity") != filters.severity:
            continue
        if filters.surgery_type and payload.get("surgery_type") != filters.surgery_type:
            continue
        if filters.year and payload.get("year") != filters.year:
            continue
        if filters.incident_type and filters.incident_type not in payload.get(
            "incident_type", []
        ):
            continue
        out.append(r)
    return out
