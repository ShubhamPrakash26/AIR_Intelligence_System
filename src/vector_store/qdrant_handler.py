"""Qdrant vector store handler for clinical incident embeddings.

Encapsulates all Qdrant client interactions: collection lifecycle management,
point upsert (single and batch), cosine-similarity search with optional
metadata filtering, and point deletion.

The Qdrant client is initialised lazily so that importing this module does not
require a running server.  Pass a pre-built ``client`` object (e.g.
``QdrantClient(location=":memory:")``) to run entirely in-memory — this is the
recommended approach for unit and integration tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.models.analysis import VectorMetadata
from src.utils.config import settings
from src.utils.logger import get_logger
from src.vector_store.metadata import build_payload

logger = get_logger(__name__)


@dataclass
class SearchResult:
    """A single result returned by a vector similarity search.

    Attributes:
        incident_id: UUID of the matched incident.
        score: Cosine similarity score (0–1; higher is more similar).
        metadata: Full Qdrant payload stored with the point.
    """

    incident_id: str
    score: float
    metadata: dict[str, Any]


class QdrantHandler:
    """Manage clinical incident vectors in a Qdrant collection.

    Args:
        url: Qdrant server URL.  Defaults to ``settings.qdrant_url``.
        api_key: Optional API key for Qdrant Cloud.
        collection_name: Name of the Qdrant collection to use.
        client: Optional pre-built QdrantClient.  When provided ``url`` and
            ``api_key`` are ignored.  Useful for injecting an in-memory client
            in tests.
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        collection_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        self._url = url or settings.qdrant_url
        self._api_key = api_key or settings.qdrant_api_key
        self._collection_name = collection_name or settings.qdrant_collection_name
        self._client = client

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def collection_name(self) -> str:
        return self._collection_name

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def ensure_collection(self, dimension: int) -> None:
        """Create the collection if it does not already exist.

        Safe to call multiple times; a no-op when the collection is present.

        Args:
            dimension: Vector dimension — must match the embedding model output.
        """
        from qdrant_client.models import Distance, VectorParams

        client = self._get_client()
        existing = {c.name for c in client.get_collections().collections}

        if self._collection_name not in existing:
            client.create_collection(
                collection_name=self._collection_name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )
            logger.info(
                "Created Qdrant collection '%s' (dimension=%d)",
                self._collection_name,
                dimension,
            )
        else:
            logger.debug("Collection '%s' already exists — skipping creation", self._collection_name)

    # ------------------------------------------------------------------
    # Upsert operations
    # ------------------------------------------------------------------

    def upsert(
        self,
        incident_id: str,
        vector: list[float],
        metadata: VectorMetadata,
    ) -> None:
        """Insert or update a single incident vector with its payload.

        Args:
            incident_id: Incident UUID string used as the Qdrant point ID.
            vector: Dense float vector from the embedding engine.
            metadata: Structured metadata stored alongside the vector.
        """
        from qdrant_client.models import PointStruct

        client = self._get_client()
        payload = {**build_payload(metadata), "incident_id": incident_id}

        client.upsert(
            collection_name=self._collection_name,
            points=[
                PointStruct(
                    id=_to_qdrant_id(incident_id),
                    vector=vector,
                    payload=payload,
                )
            ],
        )
        logger.debug(
            "Upserted incident '%s' into collection '%s'",
            incident_id,
            self._collection_name,
        )

    def upsert_batch(
        self,
        records: list[tuple[str, list[float], VectorMetadata]],
    ) -> None:
        """Insert or update multiple incident vectors in a single call.

        Args:
            records: List of ``(incident_id, vector, metadata)`` tuples.
                Empty lists are silently ignored.
        """
        if not records:
            return

        from qdrant_client.models import PointStruct

        client = self._get_client()
        points = [
            PointStruct(
                id=_to_qdrant_id(incident_id),
                vector=vector,
                payload={**build_payload(metadata), "incident_id": incident_id},
            )
            for incident_id, vector, metadata in records
        ]

        client.upsert(collection_name=self._collection_name, points=points)
        logger.info(
            "Batch-upserted %d incidents into collection '%s'",
            len(points),
            self._collection_name,
        )

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """Find the most similar incidents using simple equality filters.

        For complex filters (e.g. list-contains), use :meth:`search_with_filter`.

        Args:
            query_vector: Dense float vector to search against.
            top_k: Maximum number of results to return.
            filters: Optional dict of ``{field: value}`` equality filters
                applied as Qdrant ``must`` conditions on the payload.

        Returns:
            List of SearchResult ordered by descending similarity score.
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        qdrant_filter: Filter | None = None
        if filters:
            conditions = [
                FieldCondition(key=key, match=MatchValue(value=value))
                for key, value in filters.items()
            ]
            qdrant_filter = Filter(must=conditions)

        return self.search_with_filter(query_vector, top_k=top_k, qdrant_filter=qdrant_filter)

    def search_with_filter(
        self,
        query_vector: list[float],
        top_k: int = 5,
        qdrant_filter: Any | None = None,
    ) -> list[SearchResult]:
        """Find the most similar incidents using a pre-built Qdrant Filter.

        This is the low-level search method used internally by :meth:`search`
        and by :class:`~src.retrieval.similarity_search.SimilaritySearchEngine`
        when complex filter conditions (e.g. array-contains) are required.

        Args:
            query_vector: Dense float vector to search against.
            top_k: Maximum number of results to return.
            qdrant_filter: Optional pre-built ``qdrant_client.models.Filter``.

        Returns:
            List of SearchResult ordered by descending similarity score.
        """
        client = self._get_client()

        response = client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        return [
            SearchResult(
                incident_id=str(hit.payload.get("incident_id", hit.id)),
                score=hit.score,
                metadata=dict(hit.payload or {}),
            )
            for hit in response.points
        ]

    def search_similar_to_stored(
        self,
        incident_id: str,
        top_k: int = 5,
        exclude_self: bool = True,
    ) -> list[SearchResult]:
        """Find incidents similar to a stored one without re-embedding.

        Qdrant uses the already-stored vector for ``incident_id`` as the query
        vector, avoiding a round-trip through the embedding model.

        Args:
            incident_id: UUID of the reference incident (must already be stored).
            top_k: Number of results to return (excluding the reference itself).
            exclude_self: When True, filter out the reference incident from results.

        Returns:
            List of SearchResult ordered by descending similarity score.
        """
        from uuid import UUID as _UUID

        client = self._get_client()
        limit = top_k + 1 if exclude_self else top_k

        response = client.query_points(
            collection_name=self._collection_name,
            query=_UUID(incident_id),
            limit=limit,
            with_payload=True,
        )

        results = [
            SearchResult(
                incident_id=str(hit.payload.get("incident_id", hit.id)),
                score=hit.score,
                metadata=dict(hit.payload or {}),
            )
            for hit in response.points
        ]

        if exclude_self:
            results = [r for r in results if r.incident_id != incident_id]

        return results[:top_k]

    # ------------------------------------------------------------------
    # Delete
    # ------------------------------------------------------------------

    def delete(self, incident_id: str) -> None:
        """Remove an incident vector from the collection.

        Args:
            incident_id: UUID of the incident to delete.
        """
        from qdrant_client.models import PointIdsList

        client = self._get_client()
        client.delete(
            collection_name=self._collection_name,
            points_selector=PointIdsList(points=[_to_qdrant_id(incident_id)]),
        )
        logger.debug(
            "Deleted incident '%s' from collection '%s'",
            incident_id,
            self._collection_name,
        )

    # ------------------------------------------------------------------
    # Info
    # ------------------------------------------------------------------

    def scroll_all(self) -> list[dict[str, Any]]:
        """Retrieve every stored point (id, vector, payload) from the collection.

        Paginates through Qdrant's scroll API in batches of 100 so the full
        collection can be fetched regardless of size.  Used by the clustering
        pipeline to obtain all incident vectors in one call.

        Returns:
            List of dicts with keys ``incident_id``, ``vector``, ``metadata``.
        """
        client = self._get_client()
        records: list[dict[str, Any]] = []
        offset = None

        while True:
            result, next_offset = client.scroll(
                collection_name=self._collection_name,
                offset=offset,
                limit=100,
                with_vectors=True,
                with_payload=True,
            )
            for point in result:
                records.append(
                    {
                        "incident_id": str(point.payload.get("incident_id", point.id)),
                        "vector": list(point.vector) if point.vector else [],
                        "metadata": dict(point.payload or {}),
                    }
                )
            if next_offset is None:
                break
            offset = next_offset

        logger.debug("scroll_all: retrieved %d records from '%s'", len(records), self._collection_name)
        return records

    def collection_info(self) -> dict[str, Any]:
        """Return summary statistics for the collection.

        Returns:
            Dict with ``name``, ``vectors_count``, ``points_count``,
            and ``status`` keys.
        """
        client = self._get_client()
        info = client.get_collection(collection_name=self._collection_name)
        return {
            "name": self._collection_name,
            "vectors_count": info.indexed_vectors_count or 0,
            "points_count": info.points_count or 0,
            "status": str(info.status),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_client(self) -> Any:
        """Lazy-initialise the Qdrant client on first access."""
        if self._client is None:
            try:
                from qdrant_client import QdrantClient
            except ImportError as exc:
                raise ImportError(
                    "qdrant-client is required. Install with: poetry add qdrant-client"
                ) from exc

            logger.info("Connecting to Qdrant at %s", self._url)
            self._client = QdrantClient(
                url=self._url,
                api_key=self._api_key or None,
            )

        return self._client


def _to_qdrant_id(incident_id: str) -> str:
    """Normalise an incident UUID string for use as a Qdrant point ID.

    Qdrant accepts UUID strings and unsigned integers as point IDs.
    All incident IDs generated by ``helpers.generate_incident_id()`` are
    valid UUIDs, so they are passed through unchanged.

    Raises:
        ValueError: If ``incident_id`` is not a valid UUID.
    """
    # Validate format — raises ValueError for non-UUID strings
    UUID(incident_id)
    return incident_id
