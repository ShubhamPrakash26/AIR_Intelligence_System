"""Integration tests for Week 10 Editorial Pipeline.

Tests the full chain from InsightBatch -> EditorialEngine -> EditorialReport,
as well as the prompt builder, API serialisation, and the _dict_to_batch converter.

No real LLM or network calls are made (fake LLM injected throughout).
"""

from __future__ import annotations

from typing import Any

import pytest

from src.insights.editorial import EditorialEngine, ThemeGrouper, ToneValidator
from src.insights.editorial_models import (
    EditorialLLMResponse,
    EditorialReport,
    SectionLLMItem,
)
from src.insights.editorial_prompts import build_editorial_message, EDITORIAL_SYSTEM_PROMPT
from src.insights.models import GeneratedInsight, InsightBatch


# ---------------------------------------------------------------------------
# Fake LLM helpers
# ---------------------------------------------------------------------------


_MULTI_SECTION_RESPONSE = EditorialLLMResponse(
    executive_summary=(
        "Review of the retrieved incidents identified three thematic areas: systemic "
        "airway preparation gaps, recurring medication error patterns, and equipment "
        "readiness failures. Across all themes, latent organisational conditions "
        "played a greater role than active individual failures."
    ),
    sections=[
        SectionLLMItem(
            theme="root_cause",
            title="Latent Conditions in Airway Preparation",
            narrative=(
                "The incidents point to a persistent latent condition in pre-induction "
                "documentation practices. In three separate cases, no documented Plan B "
                "existed at the time of anaesthetic induction, consistent with an "
                "organisational norm of relying on individual experience rather than "
                "structured pre-procedural checklists. This represents a system-level "
                "vulnerability rather than a failure of technical competence."
            ),
            key_learning=(
                "Pre-induction Plan A/B documentation should be a mandatory checklist item, "
                "not an optional clinical judgement."
            ),
        ),
        SectionLLMItem(
            theme="safety_recommendations",
            title="System-Level Airway Safety Actions",
            narrative=(
                "Three complementary system-level interventions emerge from this analysis. "
                "Departments should introduce a two-column pre-induction briefing form capturing "
                "primary technique and rescue plan. Video laryngoscopy should be pre-positioned "
                "for all cases with documented Mallampati III-IV scores. Finally, a structured "
                "24-hour post-incident debrief process enables learning before detail is lost."
            ),
            key_learning=(
                "Mandatory briefing forms and pre-positioned rescue equipment are the "
                "highest-yield systemic interventions identified."
            ),
        ),
    ],
    conclusion=(
        "The incidents reviewed reflect the systemic conditions that a safety reporting culture "
        "is designed to surface. The actions identified here are achievable at department level "
        "without significant resource investment. Departments are encouraged to present these "
        "findings at the next clinical governance meeting and to share implementation outcomes "
        "with the national registry."
    ),
)


class _FakeStructuredLLM:
    def __init__(self, response: EditorialLLMResponse = _MULTI_SECTION_RESPONSE) -> None:
        self._r = response

    def invoke(self, messages: Any) -> EditorialLLMResponse:
        return self._r


class _FakeLLM:
    def __init__(self, response: EditorialLLMResponse = _MULTI_SECTION_RESPONSE) -> None:
        self._r = response

    def with_structured_output(self, schema: Any) -> _FakeStructuredLLM:
        return _FakeStructuredLLM(self._r)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------


def _make_insight(insight_type: str = "root_cause", idx: int = 0) -> GeneratedInsight:
    return GeneratedInsight(
        insight_id=f"id-{idx:03d}",
        query="airway safety patterns",
        insight_text=(
            f"Insight {idx}: specific clinical finding about the recurring pattern "
            f"in {insight_type} incidents observed across the case set."
        ),
        insight_type=insight_type,
        evidence_citations=[f"Incident abc{idx:03d} | severity=High | incident_type=Airway Event | score=0.9"],
        actionable_steps=[
            "Anaesthesiologist documents Plan A/B before induction",
            "Nurse pre-positions rescue device on first failure",
        ],
        confidence="High",
        specificity_score=0.75,
        generated_at="2026-06-13T00:00:00+00:00",
        model_version="week9-insight-generator-0.1",
    )


def _multi_theme_batch() -> InsightBatch:
    insights = [
        _make_insight("root_cause", 0),
        _make_insight("root_cause", 1),
        _make_insight("safety_recommendations", 2),
    ]
    return InsightBatch(
        query="recurring airway safety patterns",
        insights=insights,
        total=3,
        generation_confidence="High",
        evidence_count=3,
        model_version="week9-insight-generator-0.1",
    )


# ---------------------------------------------------------------------------
# Full pipeline: InsightBatch -> EditorialReport
# ---------------------------------------------------------------------------


class TestEditorialPipelineWithFakeLLM:
    def test_generate_returns_editorial_report(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        assert isinstance(report, EditorialReport)

    def test_report_has_expected_section_count(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        assert report.section_count == 2  # two sections in _MULTI_SECTION_RESPONSE

    def test_report_executive_summary_non_empty(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        assert len(report.executive_summary) > 30

    def test_report_conclusion_non_empty(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        assert len(report.conclusion) > 30

    def test_report_has_llm_narrative_true(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        assert report.has_llm_narrative is True

    def test_sections_have_narratives(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        for section in report.sections:
            assert len(section.narrative) >= 50

    def test_sections_have_key_learnings(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        for section in report.sections:
            assert len(section.key_learning) > 10

    def test_tone_score_in_range(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        assert 0.0 <= report.tone_score <= 1.0

    def test_word_count_positive(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_multi_theme_batch())
        assert report.word_count > 0

    def test_report_query_preserved(self):
        engine = EditorialEngine(llm=_FakeLLM())
        batch = _multi_theme_batch()
        report = engine.generate(batch)
        assert report.query == batch.query


# ---------------------------------------------------------------------------
# Fallback integration
# ---------------------------------------------------------------------------


class TestEditorialFallbackIntegration:
    def test_fallback_returns_valid_report(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        report = engine.generate(_multi_theme_batch())
        assert isinstance(report, EditorialReport)

    def test_fallback_section_count_matches_theme_count(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        # _multi_theme_batch has 2 themes: root_cause + safety_recommendations
        report = engine.generate(_multi_theme_batch())
        assert report.section_count == 2

    def test_fallback_narrative_uses_insight_text(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        report = engine.generate(_multi_theme_batch())
        # Fallback narrative is derived from insight_text
        assert len(report.sections[0].narrative) > 0


# ---------------------------------------------------------------------------
# Prompt builder integration
# ---------------------------------------------------------------------------


class TestEditorialPromptBuilder:
    def test_build_message_contains_query(self):
        grouper = ThemeGrouper()
        insights = [_make_insight("root_cause", 0)]
        grouped = grouper.group(insights)
        msg = build_editorial_message("difficult airway", grouped, total_incidents=1)
        assert "difficult airway" in msg

    def test_build_message_contains_theme_label(self):
        grouper = ThemeGrouper()
        insights = [_make_insight("root_cause", 0)]
        grouped = grouper.group(insights)
        msg = build_editorial_message("query", grouped, total_incidents=1)
        assert "ROOT CAUSE ANALYSIS" in msg

    def test_build_message_includes_insight_text(self):
        grouper = ThemeGrouper()
        insight = _make_insight("root_cause", 0)
        grouped = grouper.group([insight])
        msg = build_editorial_message("query", grouped, total_incidents=1)
        assert insight.insight_text[:30] in msg

    def test_build_message_includes_citations(self):
        grouper = ThemeGrouper()
        insight = _make_insight("root_cause", 0)
        grouped = grouper.group([insight])
        msg = build_editorial_message("query", grouped, total_incidents=1)
        assert "abc000" in msg

    def test_system_prompt_contains_tone_requirements(self):
        assert "TONE REQUIREMENTS" in EDITORIAL_SYSTEM_PROMPT

    def test_system_prompt_contains_forbidden_language(self):
        assert "FORBIDDEN LANGUAGE" in EDITORIAL_SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# API serialisation (_report_to_out + _dict_to_batch)
# ---------------------------------------------------------------------------


class TestAPISerialisation:
    def test_report_to_out_round_trips(self):
        from src.api.editorial import _report_to_out, EditorialReportOut
        from src.insights.editorial_models import EditorialSection

        section = EditorialSection(
            section_id="s-001",
            theme="pattern_analysis",
            title="Pattern Observations",
            narrative=(
                "Three incidents share a consistent pattern of delayed escalation "
                "to video laryngoscopy beyond the recommended two-attempt threshold."
            ),
            supporting_insights=[],
            evidence_citations=["Incident abc123 | severity=High"],
            key_learning="Pre-positioning reduces escalation delay.",
            tone_score=1.0,
            generated_at="2026-06-13T00:00:00+00:00",
            model_version="week10-editorial-engine-0.1",
        )
        report = EditorialReport(
            report_id="rep-001",
            query="airway patterns",
            title="Clinical Safety Analysis: airway patterns",
            executive_summary="Two themes identified across five incidents.",
            sections=[section],
            conclusion="Review recommended at next governance meeting.",
            total_incidents_referenced=1,
            all_citations=["Incident abc123 | severity=High"],
            tone_score=1.0,
            has_llm_narrative=True,
            generated_at="2026-06-13T00:00:00+00:00",
            model_version="week10-editorial-engine-0.1",
        )
        out = _report_to_out(report)
        assert isinstance(out, EditorialReportOut)
        assert out.section_count == 1
        assert out.grounded_section_count == 1
        assert out.has_llm_narrative is True
        assert out.all_citations == ["Incident abc123 | severity=High"]

    def test_dict_to_batch_converts_correctly(self):
        from src.api.editorial import _dict_to_batch

        data = {
            "query": "airway management",
            "insights": [
                {
                    "insight_id": "id-001",
                    "insight_text": "Specific finding about clinical pattern.",
                    "insight_type": "root_cause",
                    "evidence_citations": ["Incident A"],
                    "actionable_steps": ["Step 1", "Step 2"],
                    "confidence": "High",
                    "specificity_score": 0.75,
                    "generated_at": "2026-06-13T00:00:00+00:00",
                }
            ],
            "total": 1,
            "generation_confidence": "High",
            "evidence_count": 1,
            "model_version": "week9-insight-generator-0.1",
        }
        batch = _dict_to_batch(data)
        assert batch.query == "airway management"
        assert len(batch.insights) == 1
        assert batch.insights[0].insight_type == "root_cause"

    def test_empty_report_serialises_cleanly(self):
        from src.api.editorial import _report_to_out

        engine = EditorialEngine(llm=_FakeLLM())
        batch = InsightBatch(
            query="empty query",
            insights=[],
            total=0,
            generation_confidence="Low",
            evidence_count=0,
            model_version="v0",
        )
        report = engine.generate(batch)
        out = _report_to_out(report)
        assert out.section_count == 0
        assert out.all_citations == []
