"""Week 10: Editorial Intelligence Layer.

Transforms InsightBatch output (Week 9) into polished APSA-style editorial
reports with thematic sections, executive summaries, and quality-scored narratives.

Components:
  ThemeGrouper   — deterministic grouping of insights by intent type
  ToneValidator  — deterministic forbidden-phrase detection and tone scoring
  NarrativeBuilder — LangChain ChatAnthropic + with_structured_output for APSA prose
  EditorialEngine  — orchestrates the full editorial pipeline

Works without ANTHROPIC_API_KEY: returns a structured fallback report with
insight_text used as section narrative (readable, not APSA prose).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from src.insights.editorial_models import (
    APSAArticle,
    EditorialLLMResponse,
    EditorialReport,
    EditorialSection,
    IncidentEditorialLLMResponse,
    SectionLLMItem,
)
from src.insights.editorial_prompts import (
    APSA_INCIDENT_SYSTEM_PROMPT,
    EDITORIAL_SYSTEM_PROMPT,
    FORBIDDEN_PHRASES,
    _THEME_LABELS,
    build_editorial_message,
    build_incident_editorial_message,
)
from src.insights.models import GeneratedInsight, InsightBatch
from src.utils.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_MODEL_VERSION = "week10-editorial-engine-0.1"


# ---------------------------------------------------------------------------
# ThemeGrouper
# ---------------------------------------------------------------------------


class ThemeGrouper:
    """Group GeneratedInsight objects by their intent theme (insight_type)."""

    # Canonical order for section presentation
    _SECTION_ORDER: list[str] = [
        "root_cause",
        "pattern_analysis",
        "safety_recommendations",
        "general",
    ]

    def group(
        self, insights: list[GeneratedInsight]
    ) -> dict[str, list[GeneratedInsight]]:
        """Return ordered dict mapping theme → insight list.

        Only includes themes that have at least one insight. Order follows
        _SECTION_ORDER so the report reads: root cause → pattern → recommendations → general.

        Args:
            insights: Output of InsightBatch.insights.

        Returns:
            Ordered dict: {theme: [insight, ...]} — only non-empty themes.
        """
        buckets: dict[str, list[GeneratedInsight]] = {}
        for ins in insights:
            theme = ins.insight_type or "general"
            buckets.setdefault(theme, []).append(ins)

        # Return in canonical order, then any unknown themes at the end
        ordered: dict[str, list[GeneratedInsight]] = {}
        for theme in self._SECTION_ORDER:
            if theme in buckets:
                ordered[theme] = buckets[theme]
        for theme, group in buckets.items():
            if theme not in ordered:
                ordered[theme] = group

        return ordered


# ---------------------------------------------------------------------------
# ToneValidator
# ---------------------------------------------------------------------------


class ToneValidator:
    """Deterministic non-punitive language checker.

    Scans narrative text for forbidden phrases (blame language, platitudes, etc.)
    and returns a tone_score in [0.0, 1.0] where 1.0 = no violations found.

    Never raises and never blocks output — it only annotates.
    """

    def validate(self, text: str) -> tuple[float, list[str]]:
        """Check text for forbidden phrases.

        Args:
            text: Narrative text to validate.

        Returns:
            (tone_score, found_phrases) where tone_score is 1.0 when clean
            and decreases by 0.15 per unique forbidden phrase found (min 0.0).
        """
        lower = text.lower()
        found: list[str] = []
        for phrase in FORBIDDEN_PHRASES:
            if phrase.lower() in lower and phrase not in found:
                found.append(phrase.strip())

        score = max(0.0, round(1.0 - len(found) * 0.15, 2))
        return score, found


# ---------------------------------------------------------------------------
# NarrativeBuilder
# ---------------------------------------------------------------------------


class NarrativeBuilder:
    """Build APSA-style narrative sections using an LLM.

    Args:
        llm: Optional pre-built LLM instance (for injection in tests).
            When None, tries to build from ANTHROPIC_API_KEY.
    """

    def __init__(self, llm: Any | None = None) -> None:
        self._llm: Any | None = llm if llm is not None else self._build_default_llm()
        self._structured_llm: Any | None = self._build_structured_llm(self._llm)

    @property
    def has_llm(self) -> bool:
        return self._llm is not None

    def build_report(
        self,
        grouped: dict[str, list[GeneratedInsight]],
        query: str,
        total_incidents: int,
    ) -> EditorialLLMResponse:
        """Generate the full editorial report from grouped insights.

        Makes a single LLM call that produces all sections + executive summary
        + conclusion in one coherent pass (ensuring consistent tone and no
        cross-section repetition).

        Args:
            grouped: Output of ThemeGrouper.group().
            query: Original clinical question.
            total_incidents: Total unique incidents referenced.

        Returns:
            EditorialLLMResponse with sections, executive_summary, conclusion.
        """
        from langchain_core.messages import HumanMessage, SystemMessage

        user_msg = build_editorial_message(query, grouped, total_incidents)
        messages = [
            SystemMessage(content=EDITORIAL_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ]

        if self._structured_llm is not None:
            response: EditorialLLMResponse = self._structured_llm.invoke(messages)
        else:
            raw = self._llm.invoke(messages)
            response = self._parse_raw(raw)

        return response

    def _parse_raw(self, response: Any) -> EditorialLLMResponse:
        """Parse unstructured LLM response into EditorialLLMResponse."""
        if isinstance(response, EditorialLLMResponse):
            return response

        content = getattr(response, "content", response)
        if isinstance(content, EditorialLLMResponse):
            return content

        text = str(content) if not isinstance(content, str) else content
        text = text.strip()

        # Strip markdown code fences
        if text.startswith("```"):
            parts = text.split("```")
            inner = parts[1]
            if inner.startswith("json"):
                inner = inner[4:]
            text = inner.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM editorial response was not valid JSON: {exc}\nRaw: {text[:200]}"
            ) from exc

        return EditorialLLMResponse.model_validate(data)

    def _build_default_llm(self) -> Any | None:
        if not settings.anthropic_api_key:
            return None
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            logger.warning("langchain_anthropic not installed — editorial LLM unavailable")
            return None
        return ChatAnthropic(
            model=settings.llm_model,
            max_tokens=4096,
            api_key=settings.anthropic_api_key,
            temperature=0.4,  # slightly higher than insights for prose fluency
        )

    def _build_structured_llm(self, llm: Any | None) -> Any | None:
        if llm is None:
            return None
        fn = getattr(llm, "with_structured_output", None)
        if not callable(fn):
            return None
        try:
            return fn(EditorialLLMResponse)
        except Exception:
            return None


# ---------------------------------------------------------------------------
# EditorialEngine
# ---------------------------------------------------------------------------


class EditorialEngine:
    """Orchestrate the full editorial pipeline.

    Pipeline:
      InsightBatch
        → ThemeGrouper (group by intent type)
        → NarrativeBuilder (LLM prose generation or fallback)
        → ToneValidator (forbidden phrase scoring)
        → EditorialReport

    Usage (production):
        engine = EditorialEngine()   # picks up ANTHROPIC_API_KEY from .env

    Usage (testing):
        engine = EditorialEngine(llm=mock_llm)
    """

    def __init__(self, llm: Any | None = None) -> None:
        self._grouper = ThemeGrouper()
        self._validator = ToneValidator()
        self._builder = NarrativeBuilder(llm)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(self, batch: InsightBatch) -> EditorialReport:
        """Generate an EditorialReport from an InsightBatch.

        Args:
            batch: Output of InsightGenerator.generate() or generate_from_result().

        Returns:
            EditorialReport with themed sections, executive summary, conclusion,
            tone score, and quality metadata.
        """
        if not batch.insights:
            return self._empty_report(batch.query)

        grouped = self._grouper.group(batch.insights)

        if not self._builder.has_llm:
            logger.info("No LLM available — returning deterministic fallback editorial")
            return self._fallback_report(batch.query, grouped, batch)

        return self._llm_report(batch.query, grouped, batch)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _llm_report(
        self,
        query: str,
        grouped: dict[str, list[GeneratedInsight]],
        batch: InsightBatch,
    ) -> EditorialReport:
        try:
            llm_resp = self._builder.build_report(grouped, query, batch.evidence_count)
        except Exception as exc:
            logger.exception("LLM editorial call failed, using fallback: %s", exc)
            return self._fallback_report(query, grouped, batch)

        sections = self._build_sections(llm_resp.sections, grouped)
        all_text = (
            llm_resp.executive_summary
            + " "
            + " ".join(s.narrative for s in sections)
            + " "
            + llm_resp.conclusion
        )
        tone_score, flagged = self._validator.validate(all_text)
        if flagged:
            logger.warning("Tone violations found in editorial output: %s", flagged)

        all_citations = self._collect_citations(sections)
        return EditorialReport(
            report_id=str(uuid.uuid4()),
            query=query,
            title=self._derive_title(query),
            executive_summary=llm_resp.executive_summary,
            sections=sections,
            conclusion=llm_resp.conclusion,
            total_incidents_referenced=len(all_citations),
            all_citations=all_citations,
            tone_score=tone_score,
            has_llm_narrative=True,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_version=_MODEL_VERSION,
            evocative_title=llm_resp.evocative_title or "",
            clinical_references=list(llm_resp.clinical_references),
        )

    def _build_sections(
        self,
        llm_items: list[SectionLLMItem],
        grouped: dict[str, list[GeneratedInsight]],
    ) -> list[EditorialSection]:
        sections: list[EditorialSection] = []
        for item in llm_items:
            insights = grouped.get(item.theme, [])
            citations = list(
                dict.fromkeys(c for ins in insights for c in ins.evidence_citations)
            )
            tone_score, _ = self._validator.validate(item.narrative)
            sections.append(
                EditorialSection(
                    section_id=str(uuid.uuid4()),
                    theme=item.theme,
                    title=item.title,
                    narrative=item.narrative,
                    supporting_insights=insights,
                    evidence_citations=citations,
                    key_learning=item.key_learning,
                    tone_score=tone_score,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    model_version=_MODEL_VERSION,
                )
            )
        return sections

    # ------------------------------------------------------------------
    # Fallback path (no LLM)
    # ------------------------------------------------------------------

    def _fallback_report(
        self,
        query: str,
        grouped: dict[str, list[GeneratedInsight]],
        batch: InsightBatch,
    ) -> EditorialReport:
        sections: list[EditorialSection] = []
        for theme, insights in grouped.items():
            label = _THEME_LABELS.get(theme, theme.replace("_", " ").title())
            narrative = self._fallback_narrative(insights)
            citations = list(
                dict.fromkeys(c for ins in insights for c in ins.evidence_citations)
            )
            tone_score, _ = self._validator.validate(narrative)
            sections.append(
                EditorialSection(
                    section_id=str(uuid.uuid4()),
                    theme=theme,
                    title=label,
                    narrative=narrative,
                    supporting_insights=insights,
                    evidence_citations=citations,
                    key_learning=self._fallback_key_learning(insights),
                    tone_score=tone_score,
                    generated_at=datetime.now(timezone.utc).isoformat(),
                    model_version=f"{_MODEL_VERSION}-fallback",
                )
            )

        all_citations = self._collect_citations(sections)
        executive_summary = (
            f"Analysis of {batch.evidence_count} supporting incident(s) for query: "
            f"'{query}' identified {len(sections)} thematic area(s) requiring attention. "
            f"LLM-generated narrative is unavailable; structured findings are presented below."
        )
        conclusion = (
            f"The {len(sections)} theme(s) identified warrant review at the next "
            f"clinical governance meeting. Activating the LLM via ANTHROPIC_API_KEY "
            f"will generate full APSA-style narrative for each section."
        )

        return EditorialReport(
            report_id=str(uuid.uuid4()),
            query=query,
            title=self._derive_title(query),
            executive_summary=executive_summary,
            sections=sections,
            conclusion=conclusion,
            total_incidents_referenced=len(all_citations),
            all_citations=all_citations,
            tone_score=1.0,  # deterministic fallback has no forbidden phrases
            has_llm_narrative=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_version=f"{_MODEL_VERSION}-fallback",
        )

    @staticmethod
    def _fallback_narrative(insights: list[GeneratedInsight]) -> str:
        if not insights:
            return "No insights available for this theme."
        parts = [ins.insight_text for ins in insights[:3]]
        return " ".join(parts)

    @staticmethod
    def _fallback_key_learning(insights: list[GeneratedInsight]) -> str:
        for ins in insights:
            if ins.actionable_steps:
                return ins.actionable_steps[0]
        return "Review the cited incidents in a structured multidisciplinary format."

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_citations(sections: list[EditorialSection]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for s in sections:
            for c in s.evidence_citations:
                if c not in seen:
                    seen.add(c)
                    result.append(c)
        return result

    @staticmethod
    def _derive_title(query: str) -> str:
        truncated = query.strip()[:60]
        if not truncated.endswith((".", "?", "!")):
            truncated = truncated.rstrip(",;: ")
        return f"Clinical Safety Analysis: {truncated}"

    def _empty_report(self, query: str) -> EditorialReport:
        return EditorialReport(
            report_id=str(uuid.uuid4()),
            query=query,
            title=self._derive_title(query),
            executive_summary="No insights provided. Ingest data and generate insights first.",
            sections=[],
            conclusion="No editorial content could be generated without supporting insights.",
            total_incidents_referenced=0,
            all_citations=[],
            tone_score=1.0,
            has_llm_narrative=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_version=_MODEL_VERSION,
        )


# ---------------------------------------------------------------------------
# IncidentEditorialEngine
# ---------------------------------------------------------------------------


_INCIDENT_MODEL_VERSION = "week12-newsletter-0.1"


class IncidentEditorialEngine:
    """Generate a single APSA-style educational article from one incident's metadata.

    Used by the newsletter endpoint to produce per-incident articles for monthly
    publication. Each call produces one ``APSAArticle`` with an evocative title,
    case vignette, educational body paragraphs, and academic references.

    Args:
        llm: Optional pre-built LLM instance (for injection in tests).
    """

    def __init__(self, llm: Any | None = None) -> None:
        self._llm: Any | None = llm if llm is not None else self._build_default_llm()
        self._structured_llm: Any | None = self._build_structured_llm()

    @property
    def has_llm(self) -> bool:
        return self._llm is not None

    def generate_article(self, metadata: dict) -> APSAArticle:
        """Generate one APSA article from a Qdrant incident metadata payload.

        Args:
            metadata: Dict with keys incident_id, incident_type, severity,
                surgery_type, root_cause, key_learning, month, year.

        Returns:
            APSAArticle ready for the newsletter formatter.
        """
        incident_id = metadata.get("incident_id", "unknown")

        if not self.has_llm:
            return self._fallback_article(metadata)

        from langchain_core.messages import HumanMessage, SystemMessage

        messages = [
            SystemMessage(content=APSA_INCIDENT_SYSTEM_PROMPT),
            HumanMessage(content=build_incident_editorial_message(metadata)),
        ]

        try:
            response: IncidentEditorialLLMResponse = self._structured_llm.invoke(messages)
        except Exception as exc:
            logger.warning("IncidentEditorialEngine LLM call failed: %s", exc)
            return self._fallback_article(metadata)

        return APSAArticle(
            article_id=str(uuid.uuid4()),
            incident_id=incident_id,
            title=response.evocative_title,
            vignette=response.vignette,
            body="\n\n".join(response.body_paragraphs),
            clinical_references=list(response.clinical_references),
            incident_metadata=metadata,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_version=_INCIDENT_MODEL_VERSION,
        )

    def _fallback_article(self, metadata: dict) -> APSAArticle:
        incident_types = metadata.get("incident_type", [])
        type_str = (
            ", ".join(incident_types) if isinstance(incident_types, list) and incident_types
            else str(incident_types) if incident_types else "Clinical Incident"
        )
        severity = metadata.get("severity", "") or "unspecified severity"
        surgery_type = metadata.get("surgery_type", "") or "perioperative"
        root_cause = metadata.get("root_cause", "") or "Root cause pending analysis."
        key_learning = metadata.get("key_learning", "") or "Review incident for learning points."

        title = f"{type_str.upper()}: A CLINICAL LEARNING OPPORTUNITY"
        vignette = (
            f"A {severity.lower()} {type_str.lower()} incident was reported in the "
            f"{surgery_type} context. {root_cause}"
        )
        body = (
            f"{type_str} incidents in the {surgery_type} setting represent a recurring "
            f"patient safety concern requiring structured perioperative planning.\n\n"
            f"{key_learning}"
        )
        return APSAArticle(
            article_id=str(uuid.uuid4()),
            incident_id=metadata.get("incident_id", "unknown"),
            title=title,
            vignette=vignette,
            body=body,
            clinical_references=[],
            incident_metadata=metadata,
            generated_at=datetime.now(timezone.utc).isoformat(),
            model_version=f"{_INCIDENT_MODEL_VERSION}-fallback",
        )

    def _build_default_llm(self) -> Any | None:
        if not settings.anthropic_api_key:
            return None
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError:
            return None
        return ChatAnthropic(
            model=settings.llm_model,
            max_tokens=4096,
            api_key=settings.anthropic_api_key,
            temperature=0.4,
        )

    def _build_structured_llm(self) -> Any | None:
        if self._llm is None:
            return None
        fn = getattr(self._llm, "with_structured_output", None)
        if not callable(fn):
            return None
        try:
            return fn(IncidentEditorialLLMResponse)
        except Exception:
            return None
