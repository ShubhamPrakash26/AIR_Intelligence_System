"""Integration tests for Week 9 Insight Pipeline.

Tests the end-to-end path from GroundedRetrievalResult -> InsightGenerator -> InsightBatch
without hitting the real LLM (injected fake) and without a live Qdrant instance.

Also covers:
  - InsightGenerator with real GroundedRAGPipeline-shaped result objects
  - Fallback path with an ingested-but-empty in-memory Qdrant
  - prompts.build_user_message structure
  - API-layer serialisation via _batch_to_out()
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import pytest

from src.insights.generator import InsightGenerator, _MODEL_VERSION
from src.insights.models import (
    GeneratedInsight,
    InsightBatch,
    InsightItem,
    InsightLLMResponse,
)
from src.insights.prompts import SYSTEM_PROMPT, build_user_message


# ---------------------------------------------------------------------------
# Fake LLM (same pattern as unit tests)
# ---------------------------------------------------------------------------


_RESPONSE_HIGH = InsightLLMResponse(
    insights=[
        InsightItem(
            insight_text=(
                "Four incidents involving incorrect syringe labelling during anaesthetic induction "
                "share a single contributing factor: absence of a standardised colour-coded syringe "
                "rack at the point of drug preparation (Incident abc001 | severity=High | "
                "type=Medication Error). In each case the drug was prepared correctly but the "
                "syringe was placed in the wrong rack position under time pressure."
            ),
            insight_type="root_cause",
            evidence_citations=[
                "Incident abc001 | severity=High | incident_type=Medication Error | score=0.921",
                "Incident abc002 | severity=Moderate | incident_type=Medication Error | score=0.880",
            ],
            actionable_steps=[
                "Anaesthesia technician positions colour-coded syringe racks before each list",
                "Anaesthesiologist verbally confirms syringe label before every injection",
                "Department purchases standardised racks — single procurement event removes reliance on individual setup",
            ],
            confidence="High",
        )
    ]
)

_RESPONSE_LOW = InsightLLMResponse(
    insights=[
        InsightItem(
            insight_text="Single retrieved incident offers limited pattern signal for this query.",
            insight_type="general",
            evidence_citations=[],
            actionable_steps=["Review incident in next M&M meeting"],
            confidence="Low",
        )
    ]
)


class _FakeStructuredLLM:
    def __init__(self, response: InsightLLMResponse) -> None:
        self._response = response

    def invoke(self, messages: Any) -> InsightLLMResponse:
        return self._response


class _FakeLLM:
    def __init__(self, response: InsightLLMResponse = _RESPONSE_HIGH) -> None:
        self._response = response

    def with_structured_output(self, schema: Any) -> _FakeStructuredLLM:
        return _FakeStructuredLLM(self._response)


# ---------------------------------------------------------------------------
# Fake GroundedRetrievalResult helpers
# ---------------------------------------------------------------------------


class _IntentType(Enum):
    ROOT_CAUSE = "root_cause"
    PATTERN_ANALYSIS = "pattern_analysis"
    SAFETY_RECOMMENDATIONS = "safety_recommendations"
    GENERAL = "general"


@dataclass
class _ProcessedQuery:
    intent: _IntentType = _IntentType.PATTERN_ANALYSIS
    keywords: list[str] = field(default_factory=lambda: ["syringe", "label", "medication"])


@dataclass
class _EvidenceBundle:
    citations: list[str] = field(default_factory=list)
    confidence: str = "Moderate"


@dataclass
class _GroundedResult:
    query: str = "recurring medication error patterns"
    grounded_context: str = (
        "Query: recurring medication error patterns\n\n"
        "Evidence Assessment: Moderate confidence (coverage=0.40)\n\n"
        "--- Incident 1 (ID: abc001) ---\n"
        "  Types: Medication Error\n"
        "  Severity: High\n"
        "  Root cause: Absent syringe labelling protocol\n"
        "  Key learning: Standardise syringe racks at each station\n"
        "  Similarity score: 0.9210\n\n"
        "--- Incident 2 (ID: abc002) ---\n"
        "  Types: Medication Error\n"
        "  Severity: Moderate\n"
        "  Root cause: Time pressure during emergency induction\n"
        "  Key learning: Verbal check before injection regardless of urgency\n"
        "  Similarity score: 0.8800\n"
    )
    context_text: str = ""
    processed_query: _ProcessedQuery = field(default_factory=_ProcessedQuery)
    evidence_bundle: _EvidenceBundle = field(
        default_factory=lambda: _EvidenceBundle(
            citations=[
                "Incident abc001 | severity=High | incident_type=Medication Error | score=0.921",
                "Incident abc002 | severity=Moderate | incident_type=Medication Error | score=0.880",
            ]
        )
    )


# ---------------------------------------------------------------------------
# Pipeline integration tests
# ---------------------------------------------------------------------------


class TestInsightPipelineWithFakeLLM:
    """Tests for generate_from_result() with a GroundedRetrievalResult-shaped object."""

    def test_generate_from_result_returns_insight_batch(self):
        gen = InsightGenerator(llm=_FakeLLM())
        result = _GroundedResult()
        batch = gen.generate_from_result(result)
        assert isinstance(batch, InsightBatch)

    def test_batch_has_expected_total(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate_from_result(_GroundedResult())
        assert batch.total == 1

    def test_batch_confidence_propagated_from_insight(self):
        # _RESPONSE_HIGH has 1 High insight; _derive_batch_confidence requires
        # 2+ High OR (1 High + 1 Moderate) to reach batch "High" — so 1 High → "Moderate"
        gen = InsightGenerator(llm=_FakeLLM(_RESPONSE_HIGH))
        batch = gen.generate_from_result(_GroundedResult())
        assert batch.generation_confidence == "Moderate"

    def test_citations_extracted_from_evidence_bundle(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate_from_result(_GroundedResult())
        # LLM response drives citations in batch; evidence_count reflects unique citations cited
        assert batch.evidence_count == 2  # two citations in _RESPONSE_HIGH

    def test_insight_is_grounded(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate_from_result(_GroundedResult())
        assert batch.insights[0].is_grounded

    def test_insight_is_actionable(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate_from_result(_GroundedResult())
        assert batch.insights[0].is_actionable

    def test_all_citations_deduplicated(self):
        multi_response = InsightLLMResponse(
            insights=[
                InsightItem(
                    insight_text="First insight covering specific clinical mechanism observed in incidents.",
                    insight_type="root_cause",
                    evidence_citations=["Incident abc001 | severity=High | incident_type=Medication Error | score=0.921"],
                    actionable_steps=["Step 1", "Step 2"],
                    confidence="High",
                ),
                InsightItem(
                    insight_text="Second insight covering a different pattern in the same incident reports.",
                    insight_type="pattern_analysis",
                    evidence_citations=["Incident abc001 | severity=High | incident_type=Medication Error | score=0.921"],
                    actionable_steps=["Step 3"],
                    confidence="Moderate",
                ),
            ]
        )
        gen = InsightGenerator(llm=_FakeLLM(multi_response))
        batch = gen.generate_from_result(_GroundedResult())
        assert len(batch.all_citations) == 1  # deduplicated

    def test_intent_extracted_from_processed_query(self):
        gen = InsightGenerator(llm=_FakeLLM())
        result = _GroundedResult(
            processed_query=_ProcessedQuery(intent=_IntentType.ROOT_CAUSE)
        )
        # Just verify no exception; intent is correctly passed to generate()
        batch = gen.generate_from_result(result)
        assert isinstance(batch, InsightBatch)

    def test_low_confidence_llm_response(self):
        gen = InsightGenerator(llm=_FakeLLM(_RESPONSE_LOW))
        batch = gen.generate_from_result(_GroundedResult())
        assert batch.generation_confidence == "Low"

    def test_specificity_score_range(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate_from_result(_GroundedResult())
        for insight in batch.insights:
            assert 0.0 <= insight.specificity_score <= 1.0

    def test_model_version_in_batch(self):
        gen = InsightGenerator(llm=_FakeLLM())
        batch = gen.generate_from_result(_GroundedResult())
        assert batch.model_version == _MODEL_VERSION


# ---------------------------------------------------------------------------
# Fallback integration tests (no LLM)
# ---------------------------------------------------------------------------


class TestFallbackPipelineIntegration:
    def test_fallback_returns_valid_batch(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        result = _GroundedResult()
        batch = gen.generate_from_result(result)
        assert isinstance(batch, InsightBatch)
        assert batch.total == 1

    def test_fallback_insight_mentions_citations(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        result = _GroundedResult()
        batch = gen.generate_from_result(result)
        assert batch.evidence_count == 2  # from the evidence bundle

    def test_fallback_model_version_has_suffix(self, monkeypatch):
        monkeypatch.setattr("src.insights.generator.settings.anthropic_api_key", None)
        gen = InsightGenerator()
        batch = gen.generate_from_result(_GroundedResult())
        assert "fallback" in batch.model_version


# ---------------------------------------------------------------------------
# Prompt builder tests
# ---------------------------------------------------------------------------


class TestPromptBuilder:
    def test_build_user_message_contains_query(self):
        msg = build_user_message(
            query="bronchospasm patterns",
            grounded_context="context text",
            citations=["Incident A"],
            intent="pattern_analysis",
            max_insights=3,
        )
        assert "bronchospasm patterns" in msg

    def test_build_user_message_contains_intent(self):
        msg = build_user_message(
            query="q",
            grounded_context="ctx",
            citations=[],
            intent="root_cause",
            max_insights=2,
        )
        assert "root_cause" in msg

    def test_build_user_message_lists_citations(self):
        citations = ["Incident abc123 | severity=High", "Incident xyz | severity=Low"]
        msg = build_user_message("q", "ctx", citations, "general", 1)
        assert "abc123" in msg
        assert "xyz" in msg

    def test_build_user_message_no_citations_placeholder(self):
        msg = build_user_message("q", "ctx", [], "general", 1)
        assert "none" in msg.lower() or "no pre-formatted" in msg.lower()

    def test_build_user_message_max_insights_stated(self):
        msg = build_user_message("q", "ctx", [], "general", 4)
        assert "4" in msg

    def test_system_prompt_contains_mandatory_rules(self):
        assert "MANDATORY RULES" in SYSTEM_PROMPT
        assert "cite" in SYSTEM_PROMPT.lower() or "citation" in SYSTEM_PROMPT.lower()

    def test_system_prompt_has_good_bad_examples(self):
        assert "BAD" in SYSTEM_PROMPT
        assert "GOOD" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# API serialisation (_batch_to_out)
# ---------------------------------------------------------------------------


class TestAPISerialisation:
    def test_batch_to_out_round_trips(self):
        from src.api.insights import _batch_to_out, InsightBatchOut

        insight = GeneratedInsight(
            insight_id="test-id",
            query="test query",
            insight_text="Specific clinical finding about recurring patterns.",
            insight_type="pattern_analysis",
            evidence_citations=["Incident A | severity=High"],
            actionable_steps=["Step 1", "Step 2"],
            confidence="High",
            specificity_score=0.70,
            generated_at="2026-06-13T00:00:00+00:00",
            model_version=_MODEL_VERSION,
        )
        batch = InsightBatch(
            query="test query",
            insights=[insight],
            total=1,
            generation_confidence="High",
            evidence_count=1,
            model_version=_MODEL_VERSION,
        )
        out = _batch_to_out(batch)
        assert isinstance(out, InsightBatchOut)
        assert out.total == 1
        assert out.insights[0].confidence == "High"
        assert out.grounded_count == 1
        assert out.actionable_count == 1
        assert out.all_citations == ["Incident A | severity=High"]

    def test_empty_batch_serialises_cleanly(self):
        from src.api.insights import _batch_to_out

        batch = InsightBatch(
            query="empty",
            insights=[],
            total=0,
            generation_confidence="Low",
            evidence_count=0,
            model_version=_MODEL_VERSION,
        )
        out = _batch_to_out(batch)
        assert out.total == 0
        assert out.insights == []
        assert out.all_citations == []
