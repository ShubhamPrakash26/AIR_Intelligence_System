"""Retrieval-Augmented Generation (RAG) for clinical incident intelligence.

Combines semantic similarity search with optional cross-encoder reranking to
produce a context block that can be injected directly into an LLM prompt.

Typical flow:
  1. Embed the query (text or incident object).
  2. Retrieve top-N candidates from Qdrant via SimilaritySearchEngine.
  3. Optionally rerank with CrossEncoderReranker (bge-reranker-large).
  4. Format the result set as a structured text block for LLM consumption.

The output of ``format_context()`` is intentionally plain text rather than a
structured type so it can be passed directly into any prompt template without
an adapter layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.embeddings.engine import EmbeddingEngine
from src.models.analysis import AIAnalysis
from src.models.incident import Incident
from src.retrieval.reranker import CrossEncoderReranker, RerankResult
from src.retrieval.similarity_search import (
    SearchFilters,
    SimilaritySearchEngine,
    SimilaritySearchResult,
)
from src.utils.logger import get_logger
from src.vector_store.qdrant_handler import QdrantHandler

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class RetrievedContext:
    """The full retrieval result produced by RAGRetriever.

    Attributes:
        query: The original query text used for retrieval.
        results: Ranked list of SimilaritySearchResult (pre-rerank).
        reranked: Ranked list of RerankResult when reranking was applied;
            empty list when reranking was skipped.
        was_reranked: True if reranking was performed.
        context_text: Ready-to-inject LLM context string built from results.
    """

    query: str
    results: list[SimilaritySearchResult]
    reranked: list[RerankResult] = field(default_factory=list)
    was_reranked: bool = False
    context_text: str = ""

    @property
    def final_results(self) -> list[RerankResult] | list[SimilaritySearchResult]:
        """Return reranked results if available, else initial similarity results."""
        return self.reranked if self.was_reranked else self.results

    @property
    def top_result(self) -> RerankResult | SimilaritySearchResult | None:
        """First (highest-ranked) result, or None when the result set is empty."""
        results = self.final_results
        return results[0] if results else None


# ---------------------------------------------------------------------------
# RAG Retriever
# ---------------------------------------------------------------------------


class RAGRetriever:
    """Retrieve clinically relevant historical incidents for LLM augmentation.

    Wraps SimilaritySearchEngine and CrossEncoderReranker to provide a
    one-call interface for the most common RAG patterns used in the AIR
    incident intelligence system.

    Args:
        search_engine: Configured SimilaritySearchEngine.
        reranker: Optional CrossEncoderReranker.  When None, reranking is
            disabled for all calls unless a custom reranker is provided at
            call time.
    """

    def __init__(
        self,
        search_engine: SimilaritySearchEngine,
        reranker: CrossEncoderReranker | None = None,
    ) -> None:
        self._search = search_engine
        self._reranker = reranker

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_components(
        cls,
        embedding_engine: EmbeddingEngine,
        qdrant_handler: QdrantHandler,
        reranker: CrossEncoderReranker | None = None,
    ) -> "RAGRetriever":
        """Convenience factory that wires up the full retrieval stack.

        Args:
            embedding_engine: Configured EmbeddingEngine.
            qdrant_handler: Configured QdrantHandler.
            reranker: Optional CrossEncoderReranker.

        Returns:
            Ready-to-use RAGRetriever.
        """
        search_engine = SimilaritySearchEngine(embedding_engine, qdrant_handler)
        return cls(search_engine, reranker)

    # ------------------------------------------------------------------
    # Core retrieval methods
    # ------------------------------------------------------------------

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        rerank: bool = False,
        filters: SearchFilters | None = None,
        rerank_top_k: int | None = None,
    ) -> RetrievedContext:
        """Retrieve similar incidents for a text query.

        Args:
            query: Free-text clinical query string.
            top_k: Number of initial candidates to retrieve from Qdrant.
                When reranking, more candidates improve recall at the cost
                of latency — consider passing ``top_k * 3`` and setting
                ``rerank_top_k`` to the number you ultimately want.
            rerank: Apply cross-encoder reranking to the candidates.
            filters: Optional metadata filter for initial retrieval.
            rerank_top_k: Maximum results to return after reranking.
                Defaults to ``top_k`` when None.

        Returns:
            RetrievedContext with results and formatted context text.
        """
        results = self._search.search_by_text(query, top_k=top_k, filters=filters)
        return self._build_context(query, results, rerank=rerank, rerank_top_k=rerank_top_k)

    def retrieve_for_incident(
        self,
        incident: Incident,
        analysis: AIAnalysis | None = None,
        top_k: int = 5,
        rerank: bool = False,
        filters: SearchFilters | None = None,
        rerank_top_k: int | None = None,
    ) -> RetrievedContext:
        """Retrieve incidents similar to a given incident object.

        When ``analysis`` is provided the retrieval vector is enriched with
        root-cause and key-learning information from the AI analysis, yielding
        more semantically precise matches.

        Args:
            incident: Reference incident to search from.
            analysis: Optional AI analysis for richer query embedding.
            top_k: Number of initial candidates from Qdrant.
            rerank: Apply cross-encoder reranking.
            filters: Optional metadata filter.
            rerank_top_k: Cap on final result count after reranking.

        Returns:
            RetrievedContext with results and formatted context text.
        """
        embed_text = self._search._embed.build_embed_text(incident, analysis)
        query = embed_text[:500]  # truncate for reranker document text

        results = self._search.search_by_incident(
            incident, analysis=analysis, top_k=top_k, filters=filters
        )
        return self._build_context(query, results, rerank=rerank, rerank_top_k=rerank_top_k)

    # ------------------------------------------------------------------
    # Context formatting
    # ------------------------------------------------------------------

    @staticmethod
    def format_context(
        results: list[Any],
        query: str = "",
        max_results: int | None = None,
    ) -> str:
        """Format retrieval results as an LLM-injectable context block.

        The output is plain text with one numbered section per incident.
        Each section includes the metadata fields most relevant for clinical
        reasoning (incident type, severity, root cause, key learning).

        Args:
            results: List of SimilaritySearchResult or RerankResult objects.
                Both types expose ``incident_id`` and ``metadata`` attributes.
            query: Original query (included as a header line when non-empty).
            max_results: Cap number of results rendered.  None = all.

        Returns:
            Formatted multi-line string suitable for LLM prompt injection.
        """
        if max_results is not None:
            results = results[:max_results]

        if not results:
            return "No relevant historical incidents were found."

        lines: list[str] = []

        if query:
            lines.append(f"Query: {query}")
            lines.append("")

        lines.append(f"Retrieved {len(results)} similar incident(s):")
        lines.append("")

        for i, r in enumerate(results, start=1):
            meta = r.metadata if hasattr(r, "metadata") else {}

            lines.append(f"--- Incident {i} (ID: {r.incident_id}) ---")

            if types := meta.get("incident_type"):
                if isinstance(types, list):
                    lines.append(f"  Types: {', '.join(types)}")
                else:
                    lines.append(f"  Type: {types}")

            if sev := meta.get("severity"):
                lines.append(f"  Severity: {sev}")

            if surgery := meta.get("surgery_type"):
                lines.append(f"  Surgical context: {surgery}")

            if rc := meta.get("root_cause"):
                lines.append(f"  Root cause: {rc}")

            if kl := meta.get("key_learning"):
                lines.append(f"  Key learning: {kl}")

            if pr := meta.get("preventive_recommendations"):
                lines.append(f"  Preventive recommendations: {pr}")

            # Score annotation
            if hasattr(r, "rerank_score"):
                lines.append(f"  Relevance score: {r.rerank_score:.4f} (reranked)")
            elif hasattr(r, "score"):
                lines.append(f"  Similarity score: {r.score:.4f}")

            lines.append("")

        return "\n".join(lines).rstrip()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_context(
        self,
        query: str,
        results: list[SimilaritySearchResult],
        rerank: bool,
        rerank_top_k: int | None,
    ) -> RetrievedContext:
        """Apply optional reranking and format context text."""
        ctx = RetrievedContext(query=query, results=results)

        if rerank and self._reranker is not None and results:
            ctx.reranked = self._reranker.rerank(query, results, top_k=rerank_top_k)
            ctx.was_reranked = True
            ctx.context_text = self.format_context(ctx.reranked, query=query)
        else:
            if rerank and self._reranker is None:
                logger.warning(
                    "rerank=True requested but no reranker configured — skipping reranking"
                )
            ctx.context_text = self.format_context(results, query=query)

        logger.info(
            "RAG retrieve: query='%s...' initial=%d reranked=%d",
            query[:60],
            len(results),
            len(ctx.reranked),
        )
        return ctx
