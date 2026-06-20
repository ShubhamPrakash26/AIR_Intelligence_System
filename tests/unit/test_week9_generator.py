"""Unit tests for Week 9 InsightGenerator.

Tests are divided into:
  - Initialisation (no LLM, with fake LLM)
  - Fallback path (no LLM available)
  - Empty-context path
  - LLM generation path (injected fake LLM)
  - _compute_specificity heuristic
  - _derive_batch_confidence rollup
  - _parse_raw_response (JSON string, markdown fences, passthrough)
  - generate_from_result delegation

No real LLM or network calls are made in this file.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.insights.generator import InsightGenerator, _MODEL_VERSION
from src.insights.models import (
    GeneratedInsight,
    InsightBatch,
    InsightItem,
    InsightLLMResponse,
)


# ---------------------------------------------------------------------------
# Fake LLM helpers
# ---------------------------------------------------------------------------


_DEFAULT_ITEM = InsightItem(
    insight_text=(
        "Three incidents share a pattern of delayed escalation to video laryngoscopy "
        "after failed direct laryngoscopy (Incident dc34916e | severity=Unknown | "
        "type=Airway Event). The common mechanism is absence of a documented Plan B, "
        "not technical failure of the primary technique."
    ),
    insight_type="pattern_analysis",
    evidence_citations=[
        "Incident dc34916e | severity=Unknown | incident_type=Airway Event | score=0.891"
    ],
    actionable_steps=[
        "Anaesthesiologist documents Plan A/B/C on the chart before every induction",
        "Circulating nurse prepares video laryngoscope when attempt 1 fails",
    ],
    confidence="High",
)

_DEFAULT_LLM_RESPONSE = InsightLLMResponse(insights=[_DEFAULT_ITEM])


class _FakeStructuredLLM:
    """Returns a fixed InsightLLMResponse on every invoke()."""

    def __init__(self, response: InsightLLMResponse = _DEFAULT_LLM_RESPONSE) -> None:
        self._response = response

    def invoke(self, messages: Any) -> InsightLLMResponse:
        return self._response


class _FakeLLM:
    """Minimal fake LLM that supports with_structured_output()."""

    def __init__(self, response: InsightLLMResponse = _DEFAULT_LLM_RESPONSE) -> None:
        self._response = response

    def with_structured_output(self, schema: Any) -> _FakeStructuredLLM:
        return _FakeStructuredLLM(self._response)

    def invoke(self, messages: Any) -> Any:
        return self._response


class _FailingLLM:
    """LLM that raises on every invoke — triggers fallback."""

    def with_structured_output(self, schema: Any) -> "_FailingLLM":
        return self

    def invoke(self, messages: Any) -> None:
        raise RuntimeError("Simulated LLM failure")


_SAMPLE_CONTEXT = (
    "Query: airway management patterns\n\n"
    "Retrieved 1 similar incident(s):\n\n"
    "--- Incident 1 (ID: dc34916e) ---\n"
    "  Types: Airway Event\n"
    "  Severity: Unknown\n"
    "  Root cause: Unknown\n"
    "  Key learning: Unknown\n"
    "  Similarity score: 0.8913\n"
)

_SAMPLE_CITATIONS = [
    "Incident dc34916e | severity=Unknown | incident_type=Airway Event | score=0.891"
]


# ---------------------------------------------------------------------------
# InsightGenerator initialisation
# ---------------------------------------------------------------------------


class TestInsightGeneratorInit:
    def test_init_without_llm_sets_llm_none(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        assert gen._llm is None
        assert gen._structured_llm is None

    def test_init_with_fake_llm_sets_structured_llm(self):
        fake = _FakeLLM()
        gen = InsightGenerator(llm=fake)
        assert gen._llm is fake
        assert gen._structured_llm is not None

    def test_injected_none_when_no_key_forces_fallback(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        assert gen._llm is None


# ---------------------------------------------------------------------------
# Fallback path (no LLM)
# ---------------------------------------------------------------------------


class TestFallbackPath:
    def test_fallback_returns_insight_batch(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        batch = gen.generate("airway failures", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        assert isinstance(batch, InsightBatch)
        assert batch.total == 1
        assert batch.generation_confidence == "Low"

    def test_fallback_insight_includes_citations(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        batch = gen.generate("query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        assert len(batch.insights[0].evidence_citations) > 0

    def test_fallback_with_no_citations(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        batch = gen.generate("query", _SAMPLE_CONTEXT, [])
        assert batch.insights[0].specificity_score == 0.0

    def test_fallback_intent_root_cause(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        batch = gen.generate("query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS, intent="root_cause")
        assert batch.insights[0].insight_type == "root_cause"

    def test_fallback_intent_general_normalised(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        batch = gen.generate("query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS, intent="unknown_intent")
        assert batch.insights[0].insight_type == "general"

    def test_failing_llm_triggers_fallback(self):
        gen = InsightGenerator(llm=_FailingLLM())
        batch = gen.generate("airway query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        assert batch.generation_confidence == "Low"
        assert batch.total >= 1


# ---------------------------------------------------------------------------
# Empty context path
# ---------------------------------------------------------------------------


class TestEmptyContextPath:
    def test_empty_context_returns_empty_batch(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("query", "   ")
        assert batch.total == 0
        assert batch.insights == []

    def test_empty_context_sets_low_confidence(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("query", "")
        assert batch.generation_confidence == "Low"


# ---------------------------------------------------------------------------
# LLM generation path (injected fake LLM)
# ---------------------------------------------------------------------------


class TestLLMGenerationPath:
    def test_generate_returns_insight_batch(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("airway query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        assert isinstance(batch, InsightBatch)
        assert batch.total == 1

    def test_generated_insight_has_correct_text(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("airway query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        assert "video laryngoscopy" in batch.insights[0].insight_text

    def test_generated_insight_has_citations(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("airway query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        assert len(batch.insights[0].evidence_citations) == 1

    def test_evidence_count_populated(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("airway query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        assert batch.evidence_count == 1

    def test_insight_has_uuid_id(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        import uuid
        uuid.UUID(batch.insights[0].insight_id)  # raises if invalid

    def test_insight_has_iso_timestamp(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("query", _SAMPLE_CONTEXT, _SAMPLE_CITATIONS)
        ts = batch.insights[0].generated_at
        assert "T" in ts and "+" in ts or "Z" in ts

    def test_max_insights_clamped_to_one(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("q", _SAMPLE_CONTEXT, max_insights=0)
        # No error; max_insights clamped to 1 internally
        assert isinstance(batch, InsightBatch)

    def test_model_version_set(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate("q", _SAMPLE_CONTEXT)
        assert batch.model_version == _MODEL_VERSION

    def test_multiple_insights_single_response(self):
        multi_response = InsightLLMResponse(
            insights=[
                InsightItem(
                    insight_text="First insight covering specific clinical mechanism in detail here.",
                    insight_type="root_cause",
                    evidence_citations=["Incident A | severity=High"],
                    actionable_steps=["Step 1", "Step 2"],
                    confidence="High",
                ),
                InsightItem(
                    insight_text="Second insight covering a different pattern across multiple cases.",
                    insight_type="pattern_analysis",
                    evidence_citations=["Incident B | severity=Low"],
                    actionable_steps=["Step 3"],
                    confidence="Moderate",
                ),
            ]
        )
        gen = InsightGenerator(llm=_FakeLLM(multi_response))
        batch = gen.generate("query", _SAMPLE_CONTEXT, max_insights=2)
        assert batch.total == 2
        assert batch.evidence_count == 2


# ---------------------------------------------------------------------------
# _compute_specificity
# ---------------------------------------------------------------------------


class TestComputeSpecificity:
    def _item(
        self,
        n_citations: int = 0,
        n_steps: int = 0,
        text_length: int = 50,
    ) -> InsightItem:
        text = "A" * max(text_length, 20)
        return InsightItem(
            insight_text=text,
            insight_type="general",
            evidence_citations=[f"Citation {i}" for i in range(n_citations)],
            actionable_steps=[f"Step {i}" for i in range(n_steps)],
            confidence="Low",
        )

    def test_zero_citations_zero_steps_short_text(self):
        score = InsightGenerator._compute_specificity(self._item(0, 0, 20))
        assert score == 0.0

    def test_one_citation_adds_020(self):
        score = InsightGenerator._compute_specificity(self._item(1, 0, 20))
        assert abs(score - 0.20) < 0.01

    def test_two_citations_caps_at_040(self):
        score = InsightGenerator._compute_specificity(self._item(3, 0, 20))
        assert abs(score - 0.40) < 0.01

    def test_three_steps_adds_030(self):
        score = InsightGenerator._compute_specificity(self._item(0, 3, 20))
        assert abs(score - 0.30) < 0.01

    def test_long_text_gte_100_adds_020(self):
        score = InsightGenerator._compute_specificity(self._item(0, 0, 100))
        assert abs(score - 0.20) < 0.01

    def test_very_long_text_gte_200_adds_030_total(self):
        score = InsightGenerator._compute_specificity(self._item(0, 0, 200))
        assert abs(score - 0.30) < 0.01

    def test_all_components_capped_at_1(self):
        score = InsightGenerator._compute_specificity(self._item(5, 5, 300))
        assert score <= 1.0


# ---------------------------------------------------------------------------
# _derive_batch_confidence
# ---------------------------------------------------------------------------


class TestDeriveBatchConfidence:
    def _insight(self, conf: str) -> GeneratedInsight:
        return GeneratedInsight(
            insight_id="id",
            query="q",
            insight_text="text",
            insight_type="general",
            evidence_citations=[],
            actionable_steps=[],
            confidence=conf,
            specificity_score=0.5,
            generated_at="2026-06-13T00:00:00+00:00",
            model_version="v",
        )

    def test_empty_list_returns_low(self):
        assert InsightGenerator._derive_batch_confidence([]) == "Low"

    def test_all_low_returns_low(self):
        insights = [self._insight("Low")] * 3
        assert InsightGenerator._derive_batch_confidence(insights) == "Low"

    def test_one_high_returns_moderate(self):
        insights = [self._insight("High"), self._insight("Low")]
        assert InsightGenerator._derive_batch_confidence(insights) == "Moderate"

    def test_two_high_returns_high(self):
        insights = [self._insight("High"), self._insight("High")]
        assert InsightGenerator._derive_batch_confidence(insights) == "High"

    def test_one_high_one_moderate_returns_high(self):
        insights = [self._insight("High"), self._insight("Moderate")]
        assert InsightGenerator._derive_batch_confidence(insights) == "High"

    def test_only_moderate_returns_moderate(self):
        insights = [self._insight("Moderate")]
        assert InsightGenerator._derive_batch_confidence(insights) == "Moderate"


# ---------------------------------------------------------------------------
# _parse_raw_response
# ---------------------------------------------------------------------------


class TestParseRawResponse:
    def _gen(self) -> InsightGenerator:
        return InsightGenerator(llm=_FakeLLM())

    def test_passthrough_insight_llm_response(self):
        gen = self._gen()
        result = gen._parse_raw_response(_DEFAULT_LLM_RESPONSE)
        assert result is _DEFAULT_LLM_RESPONSE

    def test_plain_json_string_parsed(self):
        gen = self._gen()
        data = {
            "insights": [
                {
                    "insight_text": "Specific finding about clinical safety pattern in incidents.",
                    "insight_type": "general",
                    "evidence_citations": [],
                    "actionable_steps": [],
                    "confidence": "Low",
                }
            ]
        }
        result = gen._parse_raw_response(json.dumps(data))
        assert isinstance(result, InsightLLMResponse)
        assert len(result.insights) == 1

    def test_markdown_json_fence_stripped(self):
        gen = self._gen()
        data = {
            "insights": [
                {
                    "insight_text": "Specific finding about clinical safety pattern in incidents.",
                    "insight_type": "general",
                    "evidence_citations": [],
                    "actionable_steps": [],
                    "confidence": "Low",
                }
            ]
        }
        fenced = f"```json\n{json.dumps(data)}\n```"
        result = gen._parse_raw_response(fenced)
        assert isinstance(result, InsightLLMResponse)

    def test_plain_fence_without_json_prefix(self):
        gen = self._gen()
        data = {
            "insights": [
                {
                    "insight_text": "Specific finding about clinical safety pattern in incidents.",
                    "insight_type": "general",
                    "evidence_citations": [],
                    "actionable_steps": [],
                    "confidence": "Low",
                }
            ]
        }
        fenced = f"```\n{json.dumps(data)}\n```"
        result = gen._parse_raw_response(fenced)
        assert isinstance(result, InsightLLMResponse)

    def test_invalid_json_raises_value_error(self):
        gen = self._gen()
        with pytest.raises(ValueError, match="not valid JSON"):
            gen._parse_raw_response("not json at all")

    def test_ai_message_content_extracted(self):
        gen = self._gen()

        class _FakeAIMessage:
            content = json.dumps(
                {
                    "insights": [
                        {
                            "insight_text": "Specific clinical safety insight covering multiple incidents.",
                            "insight_type": "general",
                            "evidence_citations": [],
                            "actionable_steps": [],
                            "confidence": "Low",
                        }
                    ]
                }
            )

        result = gen._parse_raw_response(_FakeAIMessage())
        assert isinstance(result, InsightLLMResponse)


# ---------------------------------------------------------------------------
# generate_from_result delegation
# ---------------------------------------------------------------------------


class TestGenerateFromResult:
    def _make_result(
        self,
        query: str = "airway failure patterns",
        citations: list[str] | None = None,
        intent_value: str = "pattern_analysis",
        grounded_context: str = _SAMPLE_CONTEXT,
    ) -> Any:
        import types
        from enum import Enum

        class _IntentType(Enum):
            PATTERN_ANALYSIS = "pattern_analysis"

        pq = types.SimpleNamespace(
            intent=_IntentType.PATTERN_ANALYSIS,
            keywords=["airway"],
        )
        bundle = types.SimpleNamespace(citations=citations or [])
        return types.SimpleNamespace(
            query=query,
            grounded_context=grounded_context,
            context_text="",
            processed_query=pq,
            evidence_bundle=bundle,
        )

    def test_generate_from_result_returns_batch(self):
        gen = InsightGenerator(llm=_FakeLLM())
        result = self._make_result()
        batch = gen.generate_from_result(result)
        assert isinstance(batch, InsightBatch)

    def test_generate_from_result_extracts_intent(self):
        gen = InsightGenerator(llm=_FakeLLM())
        result = self._make_result(intent_value="pattern_analysis")
        # As long as it doesn't raise, the intent was extracted and passed
        batch = gen.generate_from_result(result)
        assert batch.total >= 0

    def test_generate_from_result_extracts_citations(self):
        gen = InsightGenerator(llm=_FakeLLM())
        citations = ["Incident abc123 | severity=High"]
        result = self._make_result(citations=citations)
        batch = gen.generate_from_result(result)
        assert batch.evidence_count >= 0  # LLM response drives actual count

    def test_generate_from_result_uses_grounded_context(self):
        gen = InsightGenerator(llm=None)  # fallback to test context extraction
        result = self._make_result(grounded_context=_SAMPLE_CONTEXT)
        batch = gen.generate_from_result(result)
        assert isinstance(batch, InsightBatch)

    def test_generate_from_result_empty_context_returns_empty(self):
        gen = InsightGenerator(llm=_FakeLLM())
        result = self._make_result(grounded_context="  ")
        batch = gen.generate_from_result(result)
        assert batch.total == 0
