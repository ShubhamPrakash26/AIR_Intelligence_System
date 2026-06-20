"""Unit tests for Week 10 editorial engine components.

Covers:
  - ThemeGrouper: ordering, mixed types, single type, empty input
  - ToneValidator: clean text, forbidden phrases, score calculation
  - NarrativeBuilder: init, fallback (no LLM), LLM path with fake LLM
  - EditorialEngine: init, generate() with fake LLM, generate() fallback
  - _derive_title and _collect_citations helpers

No real LLM or network calls are made.
"""

from __future__ import annotations

from typing import Any

import pytest

from src.insights.editorial import EditorialEngine, NarrativeBuilder, ThemeGrouper, ToneValidator
from src.insights.editorial_models import (
    EditorialLLMResponse,
    EditorialReport,
    SectionLLMItem,
)
from src.insights.models import GeneratedInsight, InsightBatch


# ---------------------------------------------------------------------------
# Fake LLM helpers
# ---------------------------------------------------------------------------


_FAKE_LLM_RESPONSE = EditorialLLMResponse(
    executive_summary=(
        "Analysis of the retrieved incidents identified two thematic areas warranting "
        "systemic review: airway preparation protocols and escalation timing thresholds."
    ),
    sections=[
        SectionLLMItem(
            theme="pattern_analysis",
            title="Recurring Airway Escalation Delays",
            narrative=(
                "Across the retrieved incidents, a consistent pattern emerges in which "
                "escalation from failed primary airway technique to rescue device was "
                "delayed beyond the two-attempt threshold recommended in the DAS guidelines. "
                "This pattern was present in three of five cases involving unanticipated "
                "difficult airways, suggesting a systemic gap in pre-induction planning "
                "rather than a deficit in individual technical skill."
            ),
            key_learning=(
                "Pre-induction Plan A/B documentation reduces escalation delay across "
                "unanticipated difficult airway scenarios."
            ),
        ),
        SectionLLMItem(
            theme="safety_recommendations",
            title="System-Level Airway Safety Improvements",
            narrative=(
                "The evidence supports three system-level interventions. First, departments "
                "should adopt a mandatory two-column pre-induction briefing form that captures "
                "both the primary technique and the rescue plan. Second, video laryngoscopy "
                "should be pre-positioned at the head of the table for all cases where "
                "Mallampati III-IV is documented. Third, post-incident debriefs within 24 hours "
                "of any airway rescue event enable real-time learning before details are lost."
            ),
            key_learning=(
                "Mandatory pre-induction briefing forms and pre-positioned rescue equipment "
                "represent the highest-yield systemic interventions."
            ),
        ),
    ],
    conclusion=(
        "The incidents reviewed in this analysis reflect the kind of systemic conditions "
        "that reporting culture is designed to surface. The patterns identified here are "
        "actionable at the department level without requiring significant additional resources. "
        "We encourage departments to review these findings within their own governance structures "
        "and to share any implementation outcomes with the registry."
    ),
)


class _FakeStructuredLLM:
    def __init__(self, response: EditorialLLMResponse = _FAKE_LLM_RESPONSE) -> None:
        self._response = response

    def invoke(self, messages: Any) -> EditorialLLMResponse:
        return self._response


class _FakeLLM:
    def __init__(self, response: EditorialLLMResponse = _FAKE_LLM_RESPONSE) -> None:
        self._response = response

    def with_structured_output(self, schema: Any) -> _FakeStructuredLLM:
        return _FakeStructuredLLM(self._response)

    def invoke(self, messages: Any) -> Any:
        return self._response


class _FailingLLM:
    def with_structured_output(self, schema: Any) -> "_FailingLLM":
        return self

    def invoke(self, messages: Any) -> None:
        raise RuntimeError("Simulated editorial LLM failure")


# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------


def _make_insight(
    insight_id: str = "id-001",
    query: str = "airway management",
    insight_text: str = "Three incidents share a failure of pre-induction airway plan documentation.",
    insight_type: str = "pattern_analysis",
    citations: list[str] | None = None,
    steps: list[str] | None = None,
    confidence: str = "High",
) -> GeneratedInsight:
    return GeneratedInsight(
        insight_id=insight_id,
        query=query,
        insight_text=insight_text,
        insight_type=insight_type,
        evidence_citations=citations if citations is not None else ["Incident abc123 | severity=High"],
        actionable_steps=steps if steps is not None else [
            "Anaesthesiologist documents Plan A/B before induction",
            "Nurse prepares rescue device on first failure",
        ],
        confidence=confidence,
        specificity_score=0.75,
        generated_at="2026-06-13T00:00:00+00:00",
        model_version="week9-insight-generator-0.1",
    )


def _make_batch(
    insights: list[GeneratedInsight] | None = None,
    query: str = "recurring airway patterns",
) -> InsightBatch:
    items = insights if insights is not None else [_make_insight()]
    return InsightBatch(
        query=query,
        insights=items,
        total=len(items),
        generation_confidence="Moderate",
        evidence_count=2,
        model_version="week9-insight-generator-0.1",
    )


# ---------------------------------------------------------------------------
# ThemeGrouper
# ---------------------------------------------------------------------------


class TestThemeGrouper:
    def test_single_theme_grouped_correctly(self):
        grouper = ThemeGrouper()
        insights = [_make_insight(insight_type="root_cause") for _ in range(3)]
        grouped = grouper.group(insights)
        assert "root_cause" in grouped
        assert len(grouped["root_cause"]) == 3

    def test_multiple_themes_separated(self):
        grouper = ThemeGrouper()
        insights = [
            _make_insight("i1", insight_type="root_cause"),
            _make_insight("i2", insight_type="pattern_analysis"),
            _make_insight("i3", insight_type="safety_recommendations"),
        ]
        grouped = grouper.group(insights)
        assert len(grouped) == 3
        assert "root_cause" in grouped
        assert "pattern_analysis" in grouped
        assert "safety_recommendations" in grouped

    def test_canonical_order_root_cause_first(self):
        grouper = ThemeGrouper()
        insights = [
            _make_insight("i1", insight_type="safety_recommendations"),
            _make_insight("i2", insight_type="root_cause"),
            _make_insight("i3", insight_type="pattern_analysis"),
        ]
        grouped = grouper.group(insights)
        keys = list(grouped.keys())
        assert keys[0] == "root_cause"
        assert keys[1] == "pattern_analysis"
        assert keys[2] == "safety_recommendations"

    def test_general_last_in_order(self):
        grouper = ThemeGrouper()
        insights = [
            _make_insight("i1", insight_type="general"),
            _make_insight("i2", insight_type="root_cause"),
        ]
        grouped = grouper.group(insights)
        keys = list(grouped.keys())
        assert keys[0] == "root_cause"
        assert keys[-1] == "general"

    def test_empty_list_returns_empty_dict(self):
        grouper = ThemeGrouper()
        assert grouper.group([]) == {}

    def test_unknown_type_grouped_under_unknown_key(self):
        grouper = ThemeGrouper()
        insights = [_make_insight(insight_type="unknown_type")]
        grouped = grouper.group(insights)
        assert "unknown_type" in grouped

    def test_mixed_with_duplicates(self):
        grouper = ThemeGrouper()
        insights = [
            _make_insight("i1", insight_type="root_cause"),
            _make_insight("i2", insight_type="root_cause"),
            _make_insight("i3", insight_type="general"),
        ]
        grouped = grouper.group(insights)
        assert len(grouped["root_cause"]) == 2
        assert len(grouped["general"]) == 1


# ---------------------------------------------------------------------------
# ToneValidator
# ---------------------------------------------------------------------------


class TestToneValidator:
    def test_clean_text_returns_score_one(self):
        validator = ToneValidator()
        score, found = validator.validate(
            "Analysis of the incidents reveals a systemic gap in airway preparation protocols. "
            "The pattern suggests a latent condition in pre-induction documentation practices."
        )
        assert score == 1.0
        assert found == []

    def test_detected_blame_phrase_reduces_score(self):
        validator = ToneValidator()
        score, found = validator.validate(
            "The anaesthesiologist failed to prepare adequately for the difficult airway."
        )
        assert score < 1.0
        assert len(found) > 0

    def test_multiple_forbidden_phrases_further_reduce_score(self):
        validator = ToneValidator()
        score_one, _ = validator.validate("staff failed to act.")
        score_two, _ = validator.validate("staff failed to act. negligence was evident.")
        assert score_two <= score_one

    def test_score_never_below_zero(self):
        validator = ToneValidator()
        text = (
            "Staff failed. Negligence was evident. Incompetence led to the outcome. "
            "Carelessness and recklessness were at fault. Blame the team."
        )
        score, _ = validator.validate(text)
        assert score >= 0.0

    def test_case_insensitive_detection(self):
        validator = ToneValidator()
        score, found = validator.validate("NEGLIGENCE was the primary cause.")
        assert len(found) > 0

    def test_generic_platitude_detected(self):
        validator = ToneValidator()
        score, found = validator.validate(
            "Communication is key to preventing these errors in the future."
        )
        assert len(found) > 0

    def test_empty_text_returns_score_one(self):
        validator = ToneValidator()
        score, found = validator.validate("")
        assert score == 1.0
        assert found == []

    def test_returns_tuple_of_float_and_list(self):
        validator = ToneValidator()
        result = validator.validate("Clean narrative text about systemic conditions.")
        assert isinstance(result, tuple)
        assert isinstance(result[0], float)
        assert isinstance(result[1], list)


# ---------------------------------------------------------------------------
# NarrativeBuilder
# ---------------------------------------------------------------------------


class TestNarrativeBuilder:
    def test_init_without_llm_has_no_llm(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        builder = NarrativeBuilder()
        assert builder._llm is None
        assert not builder.has_llm

    def test_init_with_fake_llm_has_llm(self):
        builder = NarrativeBuilder(llm=_FakeLLM())
        assert builder.has_llm

    def test_parse_raw_passthrough_response(self):
        builder = NarrativeBuilder(llm=_FakeLLM())
        result = builder._parse_raw(_FAKE_LLM_RESPONSE)
        assert result is _FAKE_LLM_RESPONSE


# ---------------------------------------------------------------------------
# EditorialEngine init
# ---------------------------------------------------------------------------


class TestEditorialEngineInit:
    def test_init_creates_components(self):
        engine = EditorialEngine(llm=_FakeLLM())
        assert isinstance(engine._grouper, ThemeGrouper)
        assert isinstance(engine._validator, ToneValidator)
        assert isinstance(engine._builder, NarrativeBuilder)

    def test_init_without_llm_builder_has_no_llm(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        assert not engine._builder.has_llm


# ---------------------------------------------------------------------------
# EditorialEngine.generate() with fake LLM
# ---------------------------------------------------------------------------


class TestEditorialEngineGenerateWithLLM:
    def test_returns_editorial_report(self):
        engine = EditorialEngine(llm=_FakeLLM())
        batch = _make_batch()
        report = engine.generate(batch)
        assert isinstance(report, EditorialReport)

    def test_report_has_sections(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_make_batch())
        assert report.section_count >= 1

    def test_report_has_executive_summary(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_make_batch())
        assert len(report.executive_summary) > 20

    def test_report_has_conclusion(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_make_batch())
        assert len(report.conclusion) > 20

    def test_has_llm_narrative_true(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_make_batch())
        assert report.has_llm_narrative is True

    def test_tone_score_on_report(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_make_batch())
        assert 0.0 <= report.tone_score <= 1.0

    def test_report_id_is_uuid(self):
        import uuid
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_make_batch())
        uuid.UUID(report.report_id)  # raises if not valid UUID

    def test_report_title_contains_query(self):
        engine = EditorialEngine(llm=_FakeLLM())
        batch = _make_batch(query="airway management patterns")
        report = engine.generate(batch)
        assert "airway management" in report.title.lower()

    def test_failing_llm_falls_back_to_deterministic(self):
        engine = EditorialEngine(llm=_FailingLLM())
        report = engine.generate(_make_batch())
        assert isinstance(report, EditorialReport)
        assert report.has_llm_narrative is False

    def test_model_version_set(self):
        engine = EditorialEngine(llm=_FakeLLM())
        report = engine.generate(_make_batch())
        assert "week10" in report.model_version


# ---------------------------------------------------------------------------
# EditorialEngine.generate() fallback (no LLM)
# ---------------------------------------------------------------------------


class TestEditorialEngineGenerateFallback:
    def test_fallback_returns_report(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        report = engine.generate(_make_batch())
        assert isinstance(report, EditorialReport)

    def test_fallback_has_llm_narrative_false(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        report = engine.generate(_make_batch())
        assert report.has_llm_narrative is False

    def test_fallback_model_version_has_suffix(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        report = engine.generate(_make_batch())
        assert "fallback" in report.model_version

    def test_fallback_has_sections(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        report = engine.generate(_make_batch())
        assert report.section_count >= 1

    def test_fallback_tone_score_one(self, monkeypatch):
        monkeypatch.setattr("src.insights.editorial.settings.anthropic_api_key", None)
        engine = EditorialEngine()
        report = engine.generate(_make_batch())
        assert report.tone_score == 1.0


# ---------------------------------------------------------------------------
# Empty batch path
# ---------------------------------------------------------------------------


class TestEditorialEngineEmptyBatch:
    def test_empty_batch_returns_empty_report(self):
        engine = EditorialEngine(llm=_FakeLLM())
        batch = _make_batch(insights=[])
        report = engine.generate(batch)
        assert report.section_count == 0

    def test_empty_batch_has_no_llm_narrative(self):
        engine = EditorialEngine(llm=_FakeLLM())
        batch = _make_batch(insights=[])
        report = engine.generate(batch)
        assert report.has_llm_narrative is False

    def test_empty_batch_all_citations_empty(self):
        engine = EditorialEngine(llm=_FakeLLM())
        batch = _make_batch(insights=[])
        report = engine.generate(batch)
        assert report.all_citations == []


# ---------------------------------------------------------------------------
# Helper methods
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_derive_title_from_query(self):
        title = EditorialEngine._derive_title("difficult airway management")
        assert "Clinical Safety Analysis" in title
        assert "difficult airway" in title.lower()

    def test_derive_title_truncates_long_query(self):
        long_query = "a" * 100
        title = EditorialEngine._derive_title(long_query)
        assert len(title) < 120

    def test_collect_citations_deduplicated(self):
        from src.insights.editorial_models import EditorialSection

        s1 = EditorialSection(
            section_id="s1",
            theme="root_cause",
            title="T1",
            narrative="N",
            supporting_insights=[],
            evidence_citations=["Incident A", "Incident B"],
            key_learning="K",
            tone_score=1.0,
            generated_at="2026-06-13T00:00:00+00:00",
            model_version="v1",
        )
        s2 = EditorialSection(
            section_id="s2",
            theme="general",
            title="T2",
            narrative="N",
            supporting_insights=[],
            evidence_citations=["Incident A", "Incident C"],
            key_learning="K",
            tone_score=1.0,
            generated_at="2026-06-13T00:00:00+00:00",
            model_version="v1",
        )
        citations = EditorialEngine._collect_citations([s1, s2])
        assert len(citations) == 3
        assert citations.count("Incident A") == 1
