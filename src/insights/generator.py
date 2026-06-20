"""Week 9: Insight Generation Agent.

InsightGenerator wraps a LangChain ChatAnthropic LLM to produce APSA-quality
clinical safety insights from grounded RAG context.

Key design decisions:
- Works without ANTHROPIC_API_KEY: deterministic fallback insight returned.
- Inject any LLM for testing: InsightGenerator(llm=mock_llm).
- Follows the same ChatAnthropic + with_structured_output pattern as
  IncidentUnderstandingAgent (src/incident/understanding_agent.py).
- generate_from_result() accepts a GroundedRetrievalResult directly,
  extracting citations and intent automatically.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from src.insights.models import (
    GeneratedInsight,
    InsightBatch,
    InsightItem,
    InsightLLMResponse,
)
from src.insights.prompts import SYSTEM_PROMPT, build_user_message
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_MODEL_VERSION = "week9-insight-generator-0.1"


class InsightGenerator:
    """Generate APSA-quality clinical safety insights from grounded RAG context.

    Usage (production):
        gen = InsightGenerator()   # picks up ANTHROPIC_API_KEY from .env
        batch = gen.generate(query, grounded_context, citations, intent)

    Usage (testing — inject a mock LLM):
        gen = InsightGenerator(llm=mock_llm)

    Usage (no API key — fallback mode):
        gen = InsightGenerator()   # llm=None, returns deterministic fallback
    """

    def __init__(self, llm: Any | None = None) -> None:
        # Allow explicit None to force fallback even if a key is set
        self._llm: Any | None = llm if llm is not None else self._build_default_llm()
        self._structured_llm: Any | None = self._build_structured_llm(self._llm)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        query: str,
        grounded_context: str,
        citations: list[str] | None = None,
        intent: str = "general",
        max_insights: int = 3,
    ) -> InsightBatch:
        """Generate insights from a query and its pre-retrieved grounded context.

        Args:
            query: Clinical question being investigated.
            grounded_context: Formatted evidence block from GroundedRAGPipeline /
                EvidenceTracker.format_grounded_context().
            citations: Citation strings from EvidenceBundle.citations.  When None,
                citations are omitted from the prompt.
            intent: Query intent string from QueryPreprocessor (default: "general").
            max_insights: Desired number of insights (clamped to 1-5).

        Returns:
            InsightBatch with quality-annotated GeneratedInsight objects.
        """
        citations = citations or []
        max_insights = max(1, min(5, max_insights))

        if not grounded_context.strip():
            return self._empty_batch(query)

        if self._llm is None:
            logger.info("No LLM available — returning deterministic fallback insights")
            return self._build_fallback(query, citations, intent)

        return self._generate_with_llm(query, grounded_context, citations, intent, max_insights)

    def generate_from_result(self, result: Any, max_insights: int = 3) -> InsightBatch:
        """Generate insights directly from a GroundedRetrievalResult.

        Extracts grounded_context, citations, and intent from the result
        and delegates to generate().

        Args:
            result: GroundedRetrievalResult from GroundedRAGPipeline.retrieve().
            max_insights: Desired number of insights (clamped to 1-5).

        Returns:
            InsightBatch for the result's query.
        """
        citations: list[str] = []
        intent = "general"

        bundle = getattr(result, "evidence_bundle", None)
        if bundle is not None:
            citations = list(getattr(bundle, "citations", []))

        pq = getattr(result, "processed_query", None)
        if pq is not None:
            raw_intent = getattr(pq, "intent", "general")
            # IntentType enum → string value
            intent = raw_intent.value if hasattr(raw_intent, "value") else str(raw_intent)

        context = getattr(result, "grounded_context", None) or getattr(
            result, "context_text", ""
        )

        return self.generate(
            query=result.query,
            grounded_context=context,
            citations=citations,
            intent=intent,
            max_insights=max_insights,
        )

    # ------------------------------------------------------------------
    # LLM plumbing
    # ------------------------------------------------------------------

    def _build_default_llm(self) -> Any | None:
        if not settings.anthropic_api_key:
            return None
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            logger.warning("langchain_anthropic not installed — insight LLM unavailable")
            return None
        return ChatAnthropic(
            model=settings.llm_model,
            max_tokens=4096,
            api_key=settings.anthropic_api_key,
            temperature=0.3,  # lower temperature for factual, grounded output
        )

    def _build_structured_llm(self, llm: Any | None) -> Any | None:
        if llm is None:
            return None
        structured_fn = getattr(llm, "with_structured_output", None)
        if not callable(structured_fn):
            return None
        try:
            return structured_fn(InsightLLMResponse)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Generation
    # ------------------------------------------------------------------

    def _generate_with_llm(
        self,
        query: str,
        grounded_context: str,
        citations: list[str],
        intent: str,
        max_insights: int,
    ) -> InsightBatch:
        from langchain_core.messages import HumanMessage, SystemMessage

        user_msg = build_user_message(
            query, grounded_context, citations, intent, max_insights
        )
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]

        try:
            if self._structured_llm is not None:
                response: InsightLLMResponse = self._structured_llm.invoke(messages)
            else:
                raw = self._llm.invoke(messages)
                response = self._parse_raw_response(raw)
        except Exception as exc:
            logger.exception("LLM call failed during insight generation: %s", exc)
            return self._build_fallback(query, citations, intent)

        return self._response_to_batch(response, query, citations)

    def _parse_raw_response(self, response: Any) -> InsightLLMResponse:
        """Parse an unstructured LLM response into InsightLLMResponse.

        Handles three shapes:
          1. Already an InsightLLMResponse (structured output path).
          2. LangChain AIMessage with .content string.
          3. Raw string — strips markdown code fences then parses JSON.
        """
        if isinstance(response, InsightLLMResponse):
            return response

        content = getattr(response, "content", response)
        if isinstance(content, InsightLLMResponse):
            return content

        text = str(content) if not isinstance(content, str) else content
        text = text.strip()

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        if text.startswith("```"):
            parts = text.split("```")
            # parts[1] is the fenced block; strip leading "json\n" if present
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            text = inner.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM response was not valid JSON: {exc}\nRaw: {text[:200]}") from exc

        return InsightLLMResponse.model_validate(data)

    # ------------------------------------------------------------------
    # Batch construction
    # ------------------------------------------------------------------

    def _response_to_batch(
        self,
        response: InsightLLMResponse,
        query: str,
        citations: list[str],
    ) -> InsightBatch:
        insights = [self._item_to_insight(item, query) for item in response.insights]
        gen_conf = self._derive_batch_confidence(insights)
        evidence_count = len({c for ins in insights for c in ins.evidence_citations})
        return InsightBatch(
            query=query,
            insights=insights,
            total=len(insights),
            generation_confidence=gen_conf,
            evidence_count=evidence_count,
            model_version=_MODEL_VERSION,
        )

    def _item_to_insight(self, item: InsightItem, query: str) -> GeneratedInsight:
        spec_score = self._compute_specificity(item)
        return GeneratedInsight(
            insight_id=str(uuid.uuid4()),
            query=query,
            insight_text=item.insight_text,
            insight_type=item.insight_type,
            evidence_citations=list(item.evidence_citations),
            actionable_steps=list(item.actionable_steps),
            confidence=item.confidence,
            specificity_score=spec_score,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_version=_MODEL_VERSION,
        )

    @staticmethod
    def _compute_specificity(item: InsightItem) -> float:
        """Heuristic specificity score (0.0-1.0).

        Contributions:
          citations: up to 0.40 (0.20 per citation, max 2)
          actionable steps: up to 0.30 (0.10 per step, max 3)
          insight text length ≥100 chars: +0.20
          insight text length ≥200 chars: +0.10 additional
        """
        score = 0.0
        score += min(len(item.evidence_citations) * 0.20, 0.40)
        score += min(len(item.actionable_steps) * 0.10, 0.30)
        if len(item.insight_text) >= 100:
            score += 0.20
        if len(item.insight_text) >= 200:
            score += 0.10
        return round(min(score, 1.0), 2)

    @staticmethod
    def _derive_batch_confidence(insights: list[GeneratedInsight]) -> str:
        """Roll up individual insight confidences into a batch-level signal."""
        if not insights:
            return "Low"
        high = sum(1 for i in insights if i.confidence == "High")
        moderate = sum(1 for i in insights if i.confidence == "Moderate")
        if high >= 2 or (high >= 1 and moderate >= 1):
            return "High"
        if high >= 1 or moderate >= 1:
            return "Moderate"
        return "Low"

    # ------------------------------------------------------------------
    # Fallback and empty paths
    # ------------------------------------------------------------------

    def _build_fallback(
        self, query: str, citations: list[str], intent: str
    ) -> InsightBatch:
        """Return a minimal structured insight when no LLM is available."""
        _action_map = {
            "root_cause": "Department lead reviews cited incidents for systemic causal factors",
            "pattern_analysis": "Quality team presents cited incidents at next M&M conference",
            "safety_recommendations": "Clinical governance team maps cited incidents to existing protocols",
            "general": "Clinician reviews cited incidents in a structured case-review format",
        }
        primary_action = _action_map.get(intent, _action_map["general"])

        if citations:
            cited = "; ".join(citations[:3])
            suffix = f"Supporting evidence: {cited}."
            text = (
                f"Retrieved {len(citations)} incident(s) relevant to query: '{query}'. "
                f"Manual structured review is recommended to identify actionable safety patterns. "
                f"{suffix}"
            )
        else:
            text = (
                f"No grounded evidence available for query: '{query}'. "
                f"Ingest incident data via POST /retrieval/ingest/excel and re-run the query."
            )

        insight = GeneratedInsight(
            insight_id=str(uuid.uuid4()),
            query=query,
            insight_text=text,
            insight_type=intent if intent in (
                "root_cause", "pattern_analysis", "safety_recommendations"
            ) else "general",
            evidence_citations=citations[:5],
            actionable_steps=[
                primary_action,
                "Document key findings and present at next morbidity and mortality conference",
            ],
            confidence="Low",
            specificity_score=0.2 if citations else 0.0,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_version=f"{_MODEL_VERSION}-fallback",
        )
        return InsightBatch(
            query=query,
            insights=[insight],
            total=1,
            generation_confidence="Low",
            evidence_count=len(citations),
            model_version=f"{_MODEL_VERSION}-fallback",
        )

    def _empty_batch(self, query: str) -> InsightBatch:
        """Return an empty batch when grounded_context is blank."""
        return InsightBatch(
            query=query,
            insights=[],
            total=0,
            generation_confidence="Low",
            evidence_count=0,
            model_version=_MODEL_VERSION,
        )
