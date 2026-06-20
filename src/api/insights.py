"""Insight generation API endpoints — Week 9.

Endpoints:
  GET  /insights/status          -- LLM availability and model info
  POST /insights/generate        -- generate insights from pre-retrieved grounded context
  POST /insights/from_query      -- full pipeline: semantic search + grounding + insights
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/insights", tags=["insights"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class InsightFromContextRequest(BaseModel):
    """Generate insights from pre-retrieved grounded context."""

    query: str = Field(..., description="Clinical question being investigated")
    grounded_context: str = Field(
        ...,
        description="Formatted evidence block — copy from grounded_context field of POST /retrieval/rag/grounded response",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Citation strings from evidence_bundle.citations of the grounded RAG response",
    )
    intent: str = Field(
        "general",
        description="Query intent: root_cause | pattern_analysis | safety_recommendations | general",
    )
    max_insights: int = Field(3, ge=1, le=5, description="Number of insights to generate")


class InsightFromQueryRequest(BaseModel):
    """Full pipeline: semantic search + grounding + insight generation in one call."""

    query: str = Field(..., description="Clinical question — triggers full retrieval + insight pipeline")
    top_k: int = Field(5, ge=1, le=20)
    rerank: bool = Field(False)
    use_preprocessing: bool = Field(True)
    max_insights: int = Field(3, ge=1, le=5)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class GeneratedInsightOut(BaseModel):
    insight_id: str
    insight_text: str
    insight_type: str
    evidence_citations: list[str]
    actionable_steps: list[str]
    confidence: str
    specificity_score: float
    is_grounded: bool
    is_actionable: bool
    generated_at: str


class InsightBatchOut(BaseModel):
    query: str
    insights: list[GeneratedInsightOut]
    total: int
    generation_confidence: str
    evidence_count: int
    grounded_count: int
    actionable_count: int
    all_citations: list[str]
    model_version: str


# ---------------------------------------------------------------------------
# Module-level singleton (lazy-initialised)
# ---------------------------------------------------------------------------

_generator: Any = None


def _get_generator() -> Any:
    global _generator
    if _generator is None:
        from src.insights.generator import InsightGenerator

        _generator = InsightGenerator()
    return _generator


def _batch_to_out(batch: Any) -> InsightBatchOut:
    return InsightBatchOut(
        query=batch.query,
        insights=[
            GeneratedInsightOut(
                insight_id=i.insight_id,
                insight_text=i.insight_text,
                insight_type=i.insight_type,
                evidence_citations=i.evidence_citations,
                actionable_steps=i.actionable_steps,
                confidence=i.confidence,
                specificity_score=i.specificity_score,
                is_grounded=i.is_grounded,
                is_actionable=i.is_actionable,
                generated_at=i.generated_at,
            )
            for i in batch.insights
        ],
        total=batch.total,
        generation_confidence=batch.generation_confidence,
        evidence_count=batch.evidence_count,
        grounded_count=batch.grounded_count,
        actionable_count=batch.actionable_count,
        all_citations=batch.all_citations,
        model_version=batch.model_version,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
async def insights_status() -> dict[str, Any]:
    """Return LLM availability and model configuration.

    Use this to confirm whether the insight pipeline will call Claude or
    fall back to deterministic placeholder insights.
    """
    has_key = bool(settings.anthropic_api_key)
    return {
        "llm_available": has_key,
        "model": settings.llm_model if has_key else None,
        "fallback_mode": not has_key,
        "note": (
            "LLM is active — Claude will generate grounded, cited insights."
            if has_key
            else "No ANTHROPIC_API_KEY configured. Returns deterministic fallback insights."
        ),
    }


@router.post("/generate", response_model=InsightBatchOut)
async def generate_insights(
    req: InsightFromContextRequest = Body(...),
) -> InsightBatchOut:
    """Generate insights from pre-retrieved grounded context.

    Chain this after POST /retrieval/rag/grounded:
      1. Call POST /retrieval/rag/grounded with your query.
      2. Copy grounded_context + evidence_bundle.citations from the response.
      3. POST here with those values.

    Example body:
    ```json
    {
      "query": "why does bronchospasm recur during laparoscopic surgery",
      "grounded_context": "...(grounded_context from /retrieval/rag/grounded)...",
      "citations": ["Incident abc123 | severity=High | incident_type=Bronchospasm | score=0.91"],
      "intent": "root_cause",
      "max_insights": 3
    }
    ```
    """
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")
    if not req.grounded_context.strip():
        raise HTTPException(status_code=422, detail="grounded_context must not be empty")

    try:
        gen = _get_generator()
        batch = gen.generate(
            query=req.query,
            grounded_context=req.grounded_context,
            citations=req.citations,
            intent=req.intent,
            max_insights=req.max_insights,
        )
        return _batch_to_out(batch)
    except Exception as exc:
        logger.exception("Insight generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/from_query", response_model=InsightBatchOut)
async def insights_from_query(
    req: InsightFromQueryRequest = Body(...),
) -> InsightBatchOut:
    """Full pipeline: semantic search -> grounded RAG -> insight generation.

    Replaces the manual chain of POST /retrieval/rag/grounded + POST /insights/generate.
    Requires at least one incident to be ingested via POST /retrieval/ingest/excel first.

    Example body:
    ```json
    {
      "query": "recurring patterns in difficult airway management",
      "top_k": 5,
      "use_preprocessing": true,
      "max_insights": 3
    }
    ```
    """
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")

    try:
        from src.api.retrieval import _ensure_collection
        from src.retrieval.rag import GroundedRAGPipeline

        engine, store = _ensure_collection()
        pipeline = GroundedRAGPipeline.from_components(
            embedding_engine=engine,
            qdrant_handler=store,
        )
        result = pipeline.retrieve(
            query=req.query,
            top_k=req.top_k,
            rerank=req.rerank,
            use_preprocessing=req.use_preprocessing,
        )

        gen = _get_generator()
        batch = gen.generate_from_result(result, max_insights=req.max_insights)
        return _batch_to_out(batch)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Insight pipeline (from_query) failed")
        raise HTTPException(status_code=500, detail=str(exc))
