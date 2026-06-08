"""Cross-encoder reranker for clinical incident retrieval.

After an initial vector similarity search retrieves a candidate set, the
reranker re-scores each candidate against the original query using a
cross-encoder model (BAAI/bge-reranker-large by default).  Cross-encoders
attend jointly to both the query and the document, producing more accurate
relevance scores than cosine similarity alone — at the cost of higher latency.

Design:
  - Model loaded lazily (inject via ``model=`` in tests to avoid download)
  - ``rerank()`` returns results sorted by cross-encoder score, not cosine
  - ``threshold`` drops results whose rerank score falls below a minimum
  - ``result_to_text()`` converts a SimilaritySearchResult's metadata to the
    plain text the cross-encoder reads as the "document"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-large"


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class RerankResult:
    """A single result after cross-encoder reranking.

    Attributes:
        incident_id: UUID of the retrieved incident.
        original_rank: 1-based rank from the initial similarity search.
        rerank_rank: 1-based rank after cross-encoder reranking.
        similarity_score: Original cosine similarity score from Qdrant.
        rerank_score: Cross-encoder relevance score (higher = more relevant).
        metadata: Full payload metadata from the original search result.
    """

    incident_id: str
    original_rank: int
    rerank_rank: int
    similarity_score: float
    rerank_score: float
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Reranker
# ---------------------------------------------------------------------------


class CrossEncoderReranker:
    """Rerank similarity search results using a cross-encoder model.

    Args:
        model_name: HuggingFace identifier for a sentence-transformers
            CrossEncoder model.  Defaults to ``BAAI/bge-reranker-large``.
        model: Optional pre-built CrossEncoder instance.  When provided the
            model is used directly without downloading anything — the
            recommended approach for unit tests.
        threshold: Minimum rerank score a result must achieve to be kept.
            Results below this value are filtered out.  Defaults to ``None``
            (no filtering).
    """

    def __init__(
        self,
        model_name: str = _DEFAULT_RERANKER_MODEL,
        model: Any | None = None,
        threshold: float | None = None,
    ) -> None:
        self._model_name = model_name
        self._model = model
        self.threshold = threshold

    @property
    def model_name(self) -> str:
        return self._model_name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def rerank(
        self,
        query: str,
        results: list[Any],  # list[SimilaritySearchResult]
        top_k: int | None = None,
    ) -> list[RerankResult]:
        """Re-score and re-order similarity search results.

        Args:
            query: The original search query text.
            results: Candidate results from :class:`SimilaritySearchEngine`.
            top_k: Return at most this many results after reranking.
                ``None`` returns all results above the threshold.

        Returns:
            Ordered list of RerankResult (highest score first).
        """
        if not results:
            return []

        model = self._load_model()
        documents = [self.result_to_text(r) for r in results]

        # sentence-transformers CrossEncoder.rank() returns a list of dicts:
        # [{"corpus_id": int, "score": float}, ...]  sorted by score desc
        ranked = model.rank(query, documents, top_k=len(results))

        reranked: list[RerankResult] = []
        for new_rank, entry in enumerate(ranked, start=1):
            idx = entry["corpus_id"]
            score = float(entry["score"])

            if self.threshold is not None and score < self.threshold:
                continue

            orig = results[idx]
            reranked.append(
                RerankResult(
                    incident_id=orig.incident_id,
                    original_rank=orig.rank,
                    rerank_rank=new_rank,
                    similarity_score=orig.score,
                    rerank_score=score,
                    metadata=orig.metadata,
                )
            )

        if top_k is not None:
            reranked = reranked[:top_k]

        logger.debug(
            "Reranker: %d candidates -> %d results (threshold=%s)",
            len(results),
            len(reranked),
            self.threshold,
        )
        return reranked

    def compute_score(self, query: str, document: str) -> float:
        """Return the cross-encoder relevance score for a single (query, doc) pair.

        Useful for evaluating individual pairs without a full rerank pass.
        """
        model = self._load_model()
        scores = model.predict([[query, document]])
        return float(scores[0])

    @staticmethod
    def result_to_text(result: Any) -> str:
        """Convert a SimilaritySearchResult's metadata to plain text.

        The cross-encoder reads this as the "document" side of the
        (query, document) pair it scores.

        Args:
            result: A :class:`~src.retrieval.similarity_search.SimilaritySearchResult`
                or any object with a ``metadata`` dict attribute.

        Returns:
            A readable multi-line text string summarising the incident.
        """
        meta = result.metadata if hasattr(result, "metadata") else {}
        parts: list[str] = []

        if types := meta.get("incident_type"):
            if isinstance(types, list):
                parts.append(f"Incident types: {', '.join(types)}")
            else:
                parts.append(f"Incident type: {types}")

        if severity := meta.get("severity"):
            parts.append(f"Severity: {severity}")

        if surgery := meta.get("surgery_type"):
            parts.append(f"Surgical context: {surgery}")

        if root_cause := meta.get("root_cause"):
            parts.append(f"Root cause: {root_cause}")

        if key_learning := meta.get("key_learning"):
            parts.append(f"Key learning: {key_learning}")

        if source := meta.get("source"):
            parts.append(f"Source: {source}")

        return "\n".join(parts) if parts else "No metadata available."

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self) -> Any:
        """Lazy-load the CrossEncoder model on first use."""
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for reranking. "
                    "Install with: poetry add sentence-transformers"
                ) from exc

            logger.info("Loading reranker model '%s' …", self._model_name)
            self._model = CrossEncoder(self._model_name)
            logger.info("Reranker model loaded.")

        return self._model
