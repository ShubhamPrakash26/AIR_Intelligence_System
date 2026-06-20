"""Editorial Intelligence API endpoints — Week 10.

Endpoints:
  GET  /editorial/status          -- LLM availability and model info
  POST /editorial/generate        -- EditorialReport from a pre-generated InsightBatch
  POST /editorial/from_query      -- full pipeline: search + ground + insights + editorial
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/editorial", tags=["editorial"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class EditorialSectionOut(BaseModel):
    section_id: str
    theme: str
    title: str
    narrative: str
    evidence_citations: list[str]
    key_learning: str
    tone_score: float
    insight_count: int
    is_grounded: bool
    word_count: int
    generated_at: str


class EditorialReportOut(BaseModel):
    report_id: str
    query: str
    title: str
    executive_summary: str
    sections: list[EditorialSectionOut]
    conclusion: str
    total_incidents_referenced: int
    all_citations: list[str]
    tone_score: float
    has_llm_narrative: bool
    section_count: int
    grounded_section_count: int
    word_count: int
    generated_at: str
    model_version: str


class EditorialFromQueryRequest(BaseModel):
    """Full pipeline: semantic search -> grounding -> insights -> editorial."""

    query: str = Field(..., description="Clinical question — triggers the full pipeline")
    top_k: int = Field(5, ge=1, le=20)
    use_preprocessing: bool = Field(True)
    max_insights: int = Field(3, ge=1, le=5)


# ---------------------------------------------------------------------------
# Module-level singletons (lazy-initialised)
# ---------------------------------------------------------------------------

_engine: Any = None


def _get_engine() -> Any:
    global _engine
    if _engine is None:
        from src.insights.editorial import EditorialEngine

        _engine = EditorialEngine()
    return _engine


def _report_to_out(report: Any) -> EditorialReportOut:
    return EditorialReportOut(
        report_id=report.report_id,
        query=report.query,
        title=report.title,
        executive_summary=report.executive_summary,
        sections=[
            EditorialSectionOut(
                section_id=s.section_id,
                theme=s.theme,
                title=s.title,
                narrative=s.narrative,
                evidence_citations=s.evidence_citations,
                key_learning=s.key_learning,
                tone_score=s.tone_score,
                insight_count=s.insight_count,
                is_grounded=s.is_grounded,
                word_count=s.word_count,
                generated_at=s.generated_at,
            )
            for s in report.sections
        ],
        conclusion=report.conclusion,
        total_incidents_referenced=report.total_incidents_referenced,
        all_citations=report.all_citations,
        tone_score=report.tone_score,
        has_llm_narrative=report.has_llm_narrative,
        section_count=report.section_count,
        grounded_section_count=report.grounded_section_count,
        word_count=report.word_count,
        generated_at=report.generated_at,
        model_version=report.model_version,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status")
async def editorial_status() -> dict[str, Any]:
    """Return LLM availability and model configuration for the editorial layer."""
    has_key = bool(settings.anthropic_api_key)
    return {
        "llm_available": has_key,
        "model": settings.llm_model if has_key else None,
        "fallback_mode": not has_key,
        "note": (
            "LLM is active — Claude will generate APSA-quality narrative prose."
            if has_key
            else "No ANTHROPIC_API_KEY configured. Returns structured fallback report (no LLM narrative)."
        ),
    }


@router.post("/generate", response_model=EditorialReportOut)
async def generate_editorial(
    req: Any = Body(...),
) -> EditorialReportOut:
    """Generate an editorial report from a pre-generated InsightBatch.

    Accepts the JSON response body from POST /insights/generate or
    POST /insights/from_query directly — copy and paste it here.

    Example body (copy from /insights/from_query response):
    ```json
    {
      "query": "...",
      "insights": [...],
      "total": 3,
      "generation_confidence": "Moderate",
      "evidence_count": 2,
      ...
    }
    ```
    """
    try:
        # Convert the incoming dict to InsightBatch dataclass
        batch = _dict_to_batch(req if isinstance(req, dict) else req.model_dump())
        engine = _get_engine()
        report = engine.generate(batch)
        return _report_to_out(report)
    except Exception as exc:
        logger.exception("Editorial generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/from_query", response_model=EditorialReportOut)
async def editorial_from_query(
    req: EditorialFromQueryRequest = Body(...),
) -> EditorialReportOut:
    """Full pipeline: semantic search -> grounded RAG -> insights -> editorial report.

    Replaces the chain of /retrieval/rag/grounded + /insights/from_query + /editorial/generate.
    Requires incidents to be ingested via POST /retrieval/ingest/excel first.

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
        from src.insights.generator import InsightGenerator
        from src.retrieval.rag import GroundedRAGPipeline

        engine_emb, store = _ensure_collection()
        pipeline = GroundedRAGPipeline.from_components(
            embedding_engine=engine_emb,
            qdrant_handler=store,
        )
        result = pipeline.retrieve(
            query=req.query,
            top_k=req.top_k,
            use_preprocessing=req.use_preprocessing,
        )

        insight_gen = InsightGenerator()
        batch = insight_gen.generate_from_result(result, max_insights=req.max_insights)

        editorial_engine = _get_engine()
        report = editorial_engine.generate(batch)
        return _report_to_out(report)

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Editorial pipeline (from_query) failed")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Internal converter
# ---------------------------------------------------------------------------


def _dict_to_batch(data: dict) -> Any:
    """Convert InsightBatchOut dict to InsightBatch dataclass."""
    from src.insights.models import GeneratedInsight, InsightBatch

    insights = [
        GeneratedInsight(
            insight_id=i.get("insight_id", str(__import__("uuid").uuid4())),
            query=data.get("query", ""),
            insight_text=i.get("insight_text", ""),
            insight_type=i.get("insight_type", "general"),
            evidence_citations=i.get("evidence_citations", []),
            actionable_steps=i.get("actionable_steps", []),
            confidence=i.get("confidence", "Low"),
            specificity_score=float(i.get("specificity_score", 0.0)),
            generated_at=i.get("generated_at", ""),
            model_version=data.get("model_version", "unknown"),
        )
        for i in data.get("insights", [])
    ]
    return InsightBatch(
        query=data.get("query", ""),
        insights=insights,
        total=data.get("total", len(insights)),
        generation_confidence=data.get("generation_confidence", "Low"),
        evidence_count=data.get("evidence_count", 0),
        model_version=data.get("model_version", "unknown"),
    )
