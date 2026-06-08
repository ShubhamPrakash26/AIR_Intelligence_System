"""Retrieval API endpoints — Week 5 + Week 6 features.

Exposes embedding, vector storage, similarity search, and RAG as HTTP endpoints.

State model:
  - One EmbeddingEngine and one QdrantHandler are created lazily per process.
  - Qdrant runs **in-memory** by default (no server required).
    Set QDRANT_URL to a real server URL in .env to persist across restarts.
  - The embedding model (BGE-M3) is downloaded on the first embed call (~2 GB,
    one-time, cached by HuggingFace Hub).  Use EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
    in .env for a small (90 MB) model during development.

Endpoints:
  POST /retrieval/ingest          — embed incidents from JSON and store in Qdrant
  POST /retrieval/ingest/excel    — parse Excel, embed, and store
  POST /retrieval/search          — semantic search by text query
  POST /retrieval/search/similar  — search similar to a stored incident ID
  POST /retrieval/rag             — full RAG: search + optional rerank + format
  GET  /retrieval/status          — collection stats
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from pathlib import Path
from pydantic import BaseModel, Field
from tempfile import NamedTemporaryFile
import shutil

from src.embeddings.engine import EmbeddingEngine
from src.models.analysis import AIAnalysis
from src.models.incident import Incident
from src.retrieval.rag import RAGRetriever, RetrievedContext
from src.retrieval.similarity_search import SearchFilters, SimilaritySearchEngine
from src.utils.config import settings
from src.utils.logger import get_logger
from src.vector_store.metadata import extract_metadata
from src.vector_store.qdrant_handler import QdrantHandler

logger = get_logger(__name__)

router = APIRouter(prefix="/retrieval", tags=["retrieval"])


# ---------------------------------------------------------------------------
# Singleton components (lazy-initialised on first request)
# ---------------------------------------------------------------------------

_engine: EmbeddingEngine | None = None
_store: QdrantHandler | None = None
_initialized: bool = False


def _get_engine() -> EmbeddingEngine:
    global _engine
    if _engine is None:
        logger.info("Initialising EmbeddingEngine (model=%s) …", settings.embedding_model)
        _engine = EmbeddingEngine(model_name=settings.embedding_model)
    return _engine


def _get_store() -> QdrantHandler:
    global _store
    if _store is None:
        # Use in-memory Qdrant if no real server is configured
        qdrant_url = settings.qdrant_url
        if qdrant_url == "http://localhost:6333":
            try:
                from qdrant_client import QdrantClient
                mem_client = QdrantClient(location=":memory:")
                _store = QdrantHandler(client=mem_client)
                logger.info("Qdrant running in-memory (restart = data loss). Set QDRANT_URL to persist.")
            except ImportError:
                raise HTTPException(500, "qdrant-client not installed")
        else:
            _store = QdrantHandler(url=qdrant_url, api_key=settings.qdrant_api_key)
    return _store


def _ensure_collection() -> tuple[EmbeddingEngine, QdrantHandler]:
    engine = _get_engine()
    store = _get_store()
    global _initialized
    if not _initialized:
        store.ensure_collection(dimension=engine.dimension)
        _initialized = True
    return engine, store


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class SearchRequest(BaseModel):
    query: str = Field(..., description="Free-text clinical query")
    top_k: int = Field(5, ge=1, le=50, description="Max results to return")
    severity: str | None = Field(None, description="Filter by severity level (Low/Moderate/High/Critical)")
    surgery_type: str | None = Field(None, description="Filter by surgical specialty")
    year: int | None = Field(None, description="Filter by incident year")
    incident_type: str | None = Field(None, description="Filter by incident type (array-contains)")


class SimilarRequest(BaseModel):
    incident_id: str = Field(..., description="UUID of a stored incident")
    top_k: int = Field(5, ge=1, le=50)
    exclude_self: bool = Field(True, description="Exclude the reference incident from results")


class RAGRequest(BaseModel):
    query: str = Field(..., description="Clinical query for RAG retrieval")
    top_k: int = Field(5, ge=1, le=50)
    rerank: bool = Field(False, description="Apply cross-encoder reranking (slower, more accurate)")
    severity: str | None = None
    surgery_type: str | None = None
    year: int | None = None
    incident_type: str | None = None


class IngestResult(BaseModel):
    ingested: int
    incident_ids: list[str]
    collection: str
    dimension: int


class AnalyzedIngestRequest(BaseModel):
    """Payload for /retrieval/ingest/analyzed.

    Pair the two outputs you already have:
      - ``incidents``  = the JSON array from ``POST /incidents/ingest/excel``
      - ``analyses``   = the JSON array from ``POST /incidents/analyze/excel``
        (or from ``POST /incidents/analyze`` after passing the incidents)

    Incidents and analyses are matched by ``incident_id``.  Unmatched incidents
    are still stored but with fallback metadata (empty root_cause, etc.).
    """

    incidents: list[Incident]
    analyses: list[AIAnalysis] = Field(default_factory=list)


class SearchHit(BaseModel):
    rank: int
    incident_id: str
    score: float
    severity: str
    surgery_type: str
    incident_type: list[str]
    root_cause: str
    key_learning: str


class RAGResponse(BaseModel):
    query: str
    hits: int
    was_reranked: bool
    context_text: str
    results: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_filters(severity, surgery_type, year, incident_type) -> SearchFilters | None:
    f = SearchFilters(
        severity=severity,
        surgery_type=surgery_type,
        year=year,
        incident_type=incident_type,
    )
    return None if f.is_empty() else f


def _hit_from_result(r: Any) -> SearchHit:
    return SearchHit(
        rank=r.rank,
        incident_id=r.incident_id,
        score=round(r.score, 4),
        severity=r.metadata.get("severity", "Unknown"),
        surgery_type=r.metadata.get("surgery_type", "Unknown"),
        incident_type=r.metadata.get("incident_type", []),
        root_cause=r.metadata.get("root_cause", ""),
        key_learning=r.metadata.get("key_learning", ""),
    )


def _parse_and_embed_incidents(
    incidents: list[Incident],
    engine: EmbeddingEngine,
    store: QdrantHandler,
    analysis_map: dict[str, AIAnalysis] | None = None,
) -> list[str]:
    """Embed incidents and upsert into Qdrant. Returns list of stored IDs.

    When ``analysis_map`` is provided, each incident's embedding text and
    Qdrant payload are enriched with AI analysis fields (root_cause,
    key_learning, severity, etc.).
    """
    stored_ids = []
    for incident in incidents:
        analysis = (analysis_map or {}).get(incident.incident_id)
        result = engine.embed_incident(incident, analysis)
        metadata = extract_metadata(incident, analysis)
        store.upsert(incident.incident_id, result.vector, metadata)
        stored_ids.append(incident.incident_id)
    return stored_ids


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
async def retrieval_status() -> dict[str, Any]:
    """Return embedding model info and Qdrant collection statistics."""
    try:
        engine, store = _ensure_collection()
        info = store.collection_info()
        return {
            "embedding_model": engine.model_name,
            "embedding_dimension": engine.dimension,
            "collection": info,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest", response_model=IngestResult)
async def ingest_incidents(incidents: list[Incident] = Body(...)) -> IngestResult:
    """Embed a list of parsed incidents and store their vectors in Qdrant.

    Use this endpoint to populate the vector store before running searches.
    Send the same JSON that ``POST /incidents/ingest/excel`` returns.
    """
    if not incidents:
        raise HTTPException(status_code=400, detail="incidents list is empty")
    try:
        engine, store = _ensure_collection()
        ids = _parse_and_embed_incidents(incidents, engine, store)
        return IngestResult(
            ingested=len(ids),
            incident_ids=ids,
            collection=store.collection_name,
            dimension=engine.dimension,
        )
    except Exception as e:
        logger.exception("Ingest failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/analyzed", response_model=IngestResult)
async def ingest_with_analysis(req: AnalyzedIngestRequest) -> IngestResult:
    """Embed incidents enriched with AI analysis and store in Qdrant.

    This is the endpoint to call when you already have BOTH the parsed
    incidents AND their AI analyses.  It produces rich vector metadata
    (root_cause, key_learning, severity from analysis rather than raw Excel).

    **Workflow:**

    1. ``POST /incidents/ingest/excel``  → save the Incident JSON array
    2. ``POST /incidents/analyze``       → send that array, save AIAnalysis array
    3. ``POST /retrieval/ingest/analyzed`` → send both arrays here

    The ``analyses`` list is optional — if omitted, metadata falls back to
    raw incident fields (same as ``POST /retrieval/ingest``).

    **Example body:**
    ```json
    {
      "incidents": [ ...array from /incidents/ingest/excel... ],
      "analyses":  [ ...array from /incidents/analyze... ]
    }
    ```
    """
    if not req.incidents:
        raise HTTPException(status_code=400, detail="incidents list is empty")
    try:
        engine, store = _ensure_collection()
        analysis_map = {a.incident_id: a for a in req.analyses}
        ids = _parse_and_embed_incidents(req.incidents, engine, store, analysis_map)
        matched = sum(1 for iid in ids if iid in analysis_map)
        logger.info(
            "ingest/analyzed: %d incidents, %d matched with analysis",
            len(ids),
            matched,
        )
        return IngestResult(
            ingested=len(ids),
            incident_ids=ids,
            collection=store.collection_name,
            dimension=engine.dimension,
        )
    except Exception as e:
        logger.exception("Analyzed ingest failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/excel", response_model=IngestResult)
async def ingest_excel(file: UploadFile = File(...)) -> IngestResult:
    """Parse an Excel file, embed each incident, and store in Qdrant.

    One call does everything: parse → embed → store.
    """
    suffix = Path(file.filename).suffix or ".xlsx"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        from src.ingestion.excel_parser import ExcelParser
        parser = ExcelParser()
        incidents = parser.parse_file(tmp_path)
        engine, store = _ensure_collection()
        ids = _parse_and_embed_incidents(incidents, engine, store)
        return IngestResult(
            ingested=len(ids),
            incident_ids=ids,
            collection=store.collection_name,
            dimension=engine.dimension,
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Excel ingest failed")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


@router.post("/search")
async def search(req: SearchRequest) -> dict[str, Any]:
    """Semantic similarity search by free-text query.

    Optionally filter by severity, surgery_type, year, or incident_type.

    Example request body:
    ```json
    {
      "query": "medication labeling failure during induction",
      "top_k": 5,
      "severity": "High"
    }
    ```
    """
    try:
        engine, store = _ensure_collection()
        search_engine = SimilaritySearchEngine(engine, store)
        filters = _build_filters(req.severity, req.surgery_type, req.year, req.incident_type)
        results = search_engine.search_by_text(req.query, top_k=req.top_k, filters=filters)
        return {
            "query": req.query,
            "filters_applied": filters is not None,
            "count": len(results),
            "results": [_hit_from_result(r).model_dump() for r in results],
        }
    except Exception as e:
        logger.exception("Search failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search/similar")
async def search_similar(req: SimilarRequest) -> dict[str, Any]:
    """Find incidents similar to a stored one — no re-embedding needed.

    Qdrant uses the stored vector directly, making this very fast.

    Example request body:
    ```json
    {
      "incident_id": "550e8400-e29b-41d4-a716-446655440000",
      "top_k": 5
    }
    ```
    """
    try:
        engine, store = _ensure_collection()
        search_engine = SimilaritySearchEngine(engine, store)
        results = search_engine.search_similar_to_stored(
            incident_id=req.incident_id,
            top_k=req.top_k,
            exclude_self=req.exclude_self,
        )
        return {
            "reference_incident_id": req.incident_id,
            "count": len(results),
            "results": [_hit_from_result(r).model_dump() for r in results],
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.exception("Similar search failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/rag", response_model=RAGResponse)
async def rag_retrieve(req: RAGRequest) -> RAGResponse:
    """Full RAG retrieval: semantic search + optional reranking + formatted context.

    The ``context_text`` field is ready to inject directly into an LLM prompt.
    Set ``rerank: true`` for higher accuracy at the cost of latency (downloads
    bge-reranker-large on first use, ~1.2 GB).

    Example request body:
    ```json
    {
      "query": "airway obstruction during cardiac surgery induction",
      "top_k": 5,
      "rerank": false
    }
    ```
    """
    try:
        engine, store = _ensure_collection()
        reranker = None
        if req.rerank:
            from src.retrieval.reranker import CrossEncoderReranker
            reranker = CrossEncoderReranker()

        retriever = RAGRetriever.from_components(engine, store, reranker=reranker)
        filters = _build_filters(req.severity, req.surgery_type, req.year, req.incident_type)
        ctx = retriever.retrieve(req.query, top_k=req.top_k, rerank=req.rerank, filters=filters)

        final = ctx.final_results
        return RAGResponse(
            query=req.query,
            hits=len(final),
            was_reranked=ctx.was_reranked,
            context_text=ctx.context_text,
            results=[
                {
                    "incident_id": r.incident_id,
                    "score": round(getattr(r, "rerank_score", r.score), 4),
                    "rank": getattr(r, "rerank_rank", r.rank),
                    "metadata": r.metadata,
                }
                for r in final
            ],
        )
    except Exception as e:
        logger.exception("RAG retrieval failed")
        raise HTTPException(status_code=500, detail=str(e))
