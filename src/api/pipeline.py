"""Pipeline API — Week 11: End-to-end integration endpoints.

Exposes a unified interface that combines all previously separate steps into
single cohesive calls.  Three endpoints:

  GET  /pipeline/status   -- live health of all pipeline components
  POST /pipeline/ingest   -- Excel → AI-analyze → Qdrant (full metadata path)
  POST /pipeline/report   -- query → retrieve → insights → editorial → format

The ``/pipeline/ingest`` endpoint is the recommended production ingest path.
Unlike ``POST /retrieval/ingest/excel`` (raw ingest, unknown metadata), it runs
the Incident Understanding Agent on every incident before storage so that
severity, incident_type, root_cause, and key_learning are populated in Qdrant.
This results in higher confidence scores and richer evidence citations throughout
the downstream RAG → Insights → Editorial pipeline.

When no ANTHROPIC_API_KEY is configured, ``/pipeline/ingest`` falls back to
raw ingest (same as /retrieval/ingest/excel) and sets ``analyzed: 0``.
"""

from __future__ import annotations

import base64
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

import shutil
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


# ---------------------------------------------------------------------------
# Singleton accessor (re-uses retrieval router's components)
# ---------------------------------------------------------------------------


def _get_retrieval_components():
    from src.api.retrieval import _ensure_collection
    return _ensure_collection()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PipelineStatusResponse(BaseModel):
    embedding_model: str
    qdrant_status: str
    llm_available: bool
    llm_model: str
    fallback_mode: bool
    total_incidents: int


class PipelineIngestResult(BaseModel):
    ingested: int
    analyzed: int
    failed_analysis: int
    incident_ids: list[str]
    collection: str
    dimension: int
    note: str


class PipelineReportRequest(BaseModel):
    query: str = Field(..., description="Clinical query for the full intelligence pipeline")
    top_k: int = Field(5, ge=1, le=20, description="Incidents to retrieve from Qdrant")
    use_preprocessing: bool = Field(
        True,
        description="Run query preprocessor (intent detection, keyword extraction)",
    )
    max_insights: int = Field(3, ge=1, le=5, description="Max insights to generate per theme")
    format: Literal["json", "markdown", "excel"] = Field(
        "json",
        description=(
            '"json" — EditorialReport dict only; '
            '"markdown" — dict + APSA Markdown document; '
            '"excel" — dict + Markdown + base64-encoded Excel workbook'
        ),
    )


class PipelineReportResponse(BaseModel):
    report: dict[str, Any]
    markdown: str | None = None
    excel_base64: str | None = None
    pipeline_stages: list[str]


class NewsletterRequest(BaseModel):
    month: str | None = Field(
        None,
        description=(
            "Month filter in YYYY-MM format (e.g. '2026-06'). "
            "When omitted, selects top incidents across all stored data."
        ),
    )
    top_k: int = Field(5, ge=1, le=10, description="Number of incidents to cover")
    format: Literal["json", "markdown"] = Field(
        "json",
        description='"json" — article list only; "markdown" — list + bundled newsletter document',
    )


class NewsletterArticleOut(BaseModel):
    article_id: str
    incident_id: str
    title: str
    vignette: str
    body: str
    clinical_references: list[str]
    incident_metadata: dict[str, Any]


class NewsletterResponse(BaseModel):
    month: str
    total_articles: int
    articles: list[NewsletterArticleOut]
    newsletter_markdown: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=PipelineStatusResponse)
async def pipeline_status() -> PipelineStatusResponse:
    """Live health check across all AIR pipeline components.

    Returns the embedding model name, Qdrant readiness, LLM availability,
    fallback mode flag, and the current incident count in the vector store.
    """
    embedding_model = "unavailable"
    qdrant_status = "unavailable"
    total_incidents = 0

    try:
        engine, store = _get_retrieval_components()
        embedding_model = engine.model_name
        info = store.collection_info()
        total_incidents = (
            info.get("points_count", 0) if isinstance(info, dict) else 0
        )
        qdrant_status = "ready"
    except Exception as exc:
        logger.warning("Pipeline status check failed: %s", exc)

    llm_available = bool(settings.anthropic_api_key)
    return PipelineStatusResponse(
        embedding_model=embedding_model,
        qdrant_status=qdrant_status,
        llm_available=llm_available,
        llm_model=settings.llm_model if llm_available else "none",
        fallback_mode=not llm_available,
        total_incidents=total_incidents,
    )


@router.post("/ingest", response_model=PipelineIngestResult)
async def pipeline_ingest(file: UploadFile = File(...)) -> PipelineIngestResult:
    """Full analyzed ingest: Excel → parse → AI analyze → Qdrant.

    This is the recommended ingest path for production-quality editorial output.
    It runs the Incident Understanding Agent on every incident before storage
    so that ``severity``, ``incident_type``, ``root_cause``, and ``key_learning``
    are all populated in the Qdrant payload.

    When ``ANTHROPIC_API_KEY`` is not set the endpoint falls back to raw ingest
    (identical to ``POST /retrieval/ingest/excel``) and sets ``analyzed: 0`` in
    the response.  The vector store is still populated; editorial quality will be
    lower because metadata fields will be empty rather than AI-classified.

    **Workflow (with API key)**

    1. Parse Excel → ``Incident`` objects
    2. ``IncidentUnderstandingAgent.analyze_incident()`` → ``AIAnalysis`` per incident
    3. ``ValidationAgent.apply()`` → validated ``AIAnalysis``
    4. ``extract_metadata(incident, analysis)`` → rich ``VectorMetadata``
    5. Embed + upsert into Qdrant
    """
    suffix = Path(file.filename).suffix or ".xlsx"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        # Step 1 — Parse
        from src.ingestion.excel_parser import ExcelParser
        incidents = ExcelParser().parse_file(tmp_path)
        if not incidents:
            raise HTTPException(status_code=400, detail="No incidents found in uploaded file")

        # Step 2 — AI analysis (optional — skipped when no API key)
        analysis_map: dict[str, Any] = {}
        failed = 0
        note = "Raw ingest — no ANTHROPIC_API_KEY; metadata will be empty."

        if settings.anthropic_api_key:
            from src.incident.understanding_agent import IncidentUnderstandingAgent
            from src.validation import ValidationAgent
            agent = IncidentUnderstandingAgent()
            validator = ValidationAgent()
            for incident in incidents:
                try:
                    raw = agent.analyze_incident(incident).analysis
                    validated = validator.apply(incident, raw)
                    analysis_map[incident.incident_id] = validated
                except Exception as exc:
                    logger.warning(
                        "Analysis failed for incident %s: %s",
                        incident.incident_id,
                        exc,
                    )
                    failed += 1
            note = (
                f"Analyzed ingest — {len(analysis_map)} incidents with AI metadata, "
                f"{failed} fell back to raw."
            )

        # Step 3 — Embed + store
        from src.vector_store.metadata import extract_metadata
        engine, store = _get_retrieval_components()
        stored_ids: list[str] = []
        for incident in incidents:
            analysis = analysis_map.get(incident.incident_id)
            result = engine.embed_incident(incident, analysis)
            metadata = extract_metadata(incident, analysis)
            store.upsert(incident.incident_id, result.vector, metadata)
            stored_ids.append(incident.incident_id)

        logger.info(
            "pipeline/ingest: %d stored, %d analyzed, %d failed",
            len(stored_ids),
            len(analysis_map),
            failed,
        )
        return PipelineIngestResult(
            ingested=len(stored_ids),
            analyzed=len(analysis_map),
            failed_analysis=failed,
            incident_ids=stored_ids,
            collection=store.collection_name,
            dimension=engine.dimension,
            note=note,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Pipeline ingest failed")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


@router.post("/report", response_model=PipelineReportResponse)
async def pipeline_report(req: PipelineReportRequest) -> PipelineReportResponse:
    """Full intelligence pipeline in one call: query → editorial → formatted output.

    Runs all stages sequentially and returns the editorial report together with
    the requested output format.

    **Stages**

    1. ``GroundedRAGPipeline`` — retrieves and grades evidence
    2. ``InsightGenerator``   — generates APSA-quality clinical insights
    3. ``EditorialEngine``    — produces thematic narrative report
    4. Formatter             — converts to Markdown and/or Excel (if requested)

    **Format options**

    - ``"json"``     — report dict only (fastest)
    - ``"markdown"`` — report dict + APSA Markdown document
    - ``"excel"``    — report dict + Markdown + base64-encoded Excel workbook

    **Tip:** Ingest via ``POST /pipeline/ingest`` first to ensure AI-enriched
    metadata in Qdrant, which produces higher confidence scores and richer
    evidence citations throughout the pipeline.
    """
    if not req.query.strip():
        raise HTTPException(status_code=422, detail="query must not be empty")

    stages: list[str] = []
    try:
        # Stage 1 — Grounded retrieval
        from src.retrieval.rag import GroundedRAGPipeline
        from src.retrieval.query_preprocessor import QueryPreprocessor
        from src.retrieval.evidence import EvidenceTracker

        engine, store = _get_retrieval_components()
        grounded_pipeline = GroundedRAGPipeline.from_components(
            embedding_engine=engine,
            qdrant_handler=store,
            preprocessor=QueryPreprocessor(),
            tracker=EvidenceTracker(),
        )
        retrieval_result = grounded_pipeline.retrieve(
            query=req.query,
            top_k=req.top_k,
            use_preprocessing=req.use_preprocessing,
        )
        stages.append("retrieval")

        # Stage 2 — Insight generation
        from src.insights.generator import InsightGenerator
        batch = InsightGenerator().generate_from_result(
            retrieval_result, max_insights=req.max_insights
        )
        stages.append("insight_generation")

        # Stage 3 — Editorial
        from src.insights.editorial import EditorialEngine
        report = EditorialEngine().generate(batch)
        stages.append("editorial")

        # Stage 4 — Serialise to API model
        from src.api.editorial import _report_to_out
        report_dict = _report_to_out(report).model_dump()

        # Stage 5 — Format (conditional)
        markdown_str: str | None = None
        excel_b64: str | None = None

        if req.format in ("markdown", "excel"):
            from src.insights.formatters import MarkdownFormatter
            markdown_str = MarkdownFormatter().format(report)
            stages.append("markdown_format")

        if req.format == "excel":
            from src.insights.formatters import ExcelFormatter
            excel_b64 = base64.b64encode(ExcelFormatter().format(report)).decode()
            stages.append("excel_format")

        return PipelineReportResponse(
            report=report_dict,
            markdown=markdown_str,
            excel_base64=excel_b64,
            pipeline_stages=stages,
        )

    except HTTPException:
        raise
    except Exception as exc:
        stage = stages[-1] if stages else "init"
        logger.exception("Pipeline report failed at stage '%s'", stage)
        raise HTTPException(status_code=500, detail=str(exc))


class PDFIngestResult(BaseModel):
    ingested: int
    analyzed: int
    failed_analysis: int
    incident_ids: list[str]
    collection: str
    dimension: int
    note: str


@router.post("/ingest/pdf", response_model=PDFIngestResult)
async def pipeline_ingest_pdf(file: UploadFile = File(...)) -> PDFIngestResult:
    """Full analyzed ingest: PDF → parse → AI analyze → Qdrant.

    Accepts a single AIR Anesthesia Incident Report PDF (AIR Log format).
    Applies the doubled-character fix, maps form fields to the Incident model,
    optionally runs the Incident Understanding Agent, and upserts into Qdrant.

    Follows the same AI-enrichment pattern as ``POST /pipeline/ingest`` for
    Excel files: when ``ANTHROPIC_API_KEY`` is set, every parsed incident is
    analyzed for severity, incident_type, root_cause, and key_learning before
    storage.  Without a key the raw parsed incident is stored directly.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Uploaded file must be a PDF (.pdf extension required).",
        )

    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        from src.ingestion.pdf_parser import PDFParser

        incidents = PDFParser().parse_file(tmp_path)
        if not incidents:
            raise HTTPException(
                status_code=400,
                detail="No incidents could be parsed from the uploaded PDF.",
            )

        # Rename the source_file field to the original filename
        for inc in incidents:
            if inc.raw_data:
                inc.raw_data["source_file"] = file.filename
            if inc.metadata:
                inc.metadata.source_file = file.filename

        # AI analysis (same pattern as /pipeline/ingest)
        analysis_map: dict[str, Any] = {}
        failed = 0
        note = "Raw PDF ingest — no ANTHROPIC_API_KEY; metadata will be empty."

        if settings.anthropic_api_key:
            from src.incident.understanding_agent import IncidentUnderstandingAgent
            from src.validation import ValidationAgent

            agent = IncidentUnderstandingAgent()
            validator = ValidationAgent()
            for incident in incidents:
                try:
                    raw = agent.analyze_incident(incident).analysis
                    validated = validator.apply(incident, raw)
                    analysis_map[incident.incident_id] = validated
                except Exception as exc:
                    logger.warning(
                        "PDF ingest: analysis failed for %s: %s",
                        incident.incident_id,
                        exc,
                    )
                    failed += 1
            note = (
                f"Analyzed PDF ingest — {len(analysis_map)} incident(s) with AI metadata, "
                f"{failed} fell back to raw."
            )

        # Embed + store
        from src.vector_store.metadata import extract_metadata

        engine, store = _get_retrieval_components()
        stored_ids: list[str] = []
        for incident in incidents:
            analysis = analysis_map.get(incident.incident_id)
            result = engine.embed_incident(incident, analysis)
            metadata = extract_metadata(incident, analysis)
            store.upsert(incident.incident_id, result.vector, metadata)
            stored_ids.append(incident.incident_id)

        logger.info(
            "pipeline/ingest/pdf: %d stored, %d analyzed, %d failed",
            len(stored_ids),
            len(analysis_map),
            failed,
        )
        return PDFIngestResult(
            ingested=len(stored_ids),
            analyzed=len(analysis_map),
            failed_analysis=failed,
            incident_ids=stored_ids,
            collection=store.collection_name,
            dimension=engine.dimension,
            note=note,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("PDF ingest failed")
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


@router.post("/newsletter", response_model=NewsletterResponse)
async def generate_newsletter(req: NewsletterRequest) -> NewsletterResponse:
    """Generate a monthly APSA-style newsletter from top incidents in Qdrant.

    For each selected incident, the Incident Editorial Engine produces one
    standalone educational article: an evocative headline, an anonymous case
    vignette, flowing educational body paragraphs, and academic references.

    **Incident selection**

    - When ``month`` is provided (e.g. ``"2026-06"``): filters incidents whose
      stored year/month matches, then ranks by severity.
    - When ``month`` is omitted: ranks all stored incidents by severity.
    - Top ``top_k`` incidents are selected after filtering and ranking.

    **Format options**

    - ``"json"``     — article list only
    - ``"markdown"`` — article list + bundled newsletter Markdown document
    """
    from datetime import datetime as _dt

    try:
        engine, store = _get_retrieval_components()
    except Exception as exc:
        logger.exception("Newsletter: failed to connect to vector store")
        raise HTTPException(status_code=500, detail=f"Vector store unavailable: {exc}")

    # ── Step 1: Scroll all stored incidents ──────────────────────────────────
    try:
        all_records = store.scroll_all()
    except Exception as exc:
        logger.exception("Newsletter: scroll_all failed")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve incidents: {exc}")

    if not all_records:
        raise HTTPException(
            status_code=404,
            detail="No incidents found in the vector store. Ingest data via POST /pipeline/ingest first.",
        )

    # ── Step 2: Filter by month/year if requested ────────────────────────────
    target_month = req.month or _dt.now().strftime("%Y-%m")
    candidates = all_records

    if req.month:
        try:
            year_int = int(req.month[:4])
            month_int = int(req.month[5:7])
        except (ValueError, IndexError):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid month format '{req.month}'. Use YYYY-MM (e.g. '2026-06').",
            )

        filtered = [
            r for r in all_records
            if r["metadata"].get("year") == year_int
            and _month_matches(r["metadata"].get("month"), month_int)
        ]
        # Fall back to all data if the month filter returns nothing
        candidates = filtered if filtered else all_records
        if not filtered:
            logger.warning(
                "Newsletter: no incidents found for %s — using all %d stored incidents",
                req.month,
                len(all_records),
            )

    # ── Step 3: Sort by severity, take top_k ────────────────────────────────
    _SEV = {"High": 3, "Moderate": 2, "Low": 1}
    candidates.sort(
        key=lambda r: _SEV.get(r["metadata"].get("severity", ""), 0),
        reverse=True,
    )
    top_records = candidates[: req.top_k]

    # ── Step 4: Generate one APSA article per incident ───────────────────────
    from src.insights.editorial import IncidentEditorialEngine
    from src.insights.formatters import APSANewsletterFormatter

    incident_engine = IncidentEditorialEngine()
    articles = []
    for record in top_records:
        article = incident_engine.generate_article(record["metadata"])
        articles.append(article)

    # ── Step 5: Format ───────────────────────────────────────────────────────
    newsletter_md: str | None = None
    if req.format == "markdown":
        newsletter_md = APSANewsletterFormatter().format(articles, target_month)

    logger.info(
        "Newsletter generated: %d articles, month=%s, format=%s, llm=%s",
        len(articles),
        target_month,
        req.format,
        incident_engine.has_llm,
    )

    return NewsletterResponse(
        month=target_month,
        total_articles=len(articles),
        articles=[
            NewsletterArticleOut(
                article_id=a.article_id,
                incident_id=a.incident_id,
                title=a.title,
                vignette=a.vignette,
                body=a.body,
                clinical_references=a.clinical_references,
                incident_metadata=a.incident_metadata,
            )
            for a in articles
        ],
        newsletter_markdown=newsletter_md,
    )


def _month_matches(stored_month: Any, month_int: int) -> bool:
    """Return True if the stored month field matches the integer month number."""
    if stored_month is None:
        return False
    # Stored as int (1-12)
    if isinstance(stored_month, int):
        return stored_month == month_int
    # Stored as string — try numeric or name match
    s = str(stored_month).strip()
    if s.isdigit():
        return int(s) == month_int
    # Month name match (e.g. "June" → 6)
    _NAMES = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    return _NAMES.get(s.lower(), -1) == month_int
