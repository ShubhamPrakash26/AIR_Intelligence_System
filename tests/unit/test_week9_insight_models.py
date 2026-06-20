"""Unit tests for Week 9 insight models.

Covers:
  - InsightItem validation and field normalisation
  - InsightLLMResponse validation
  - GeneratedInsight property accessors
  - InsightBatch computed properties (all_citations, grounded_count, actionable_count)
"""

import pytest
from pydantic import ValidationError

from src.insights.models import (
    GeneratedInsight,
    InsightBatch,
    InsightItem,
    InsightLLMResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_insight(
    insight_id: str = "id-001",
    query: str = "test query",
    insight_text: str = "A specific clinical finding about the pattern in these incidents.",
    insight_type: str = "pattern_analysis",
    evidence_citations: list[str] | None = None,
    actionable_steps: list[str] | None = None,
    confidence: str = "High",
    specificity_score: float = 0.80,
    generated_at: str = "2026-06-13T00:00:00+00:00",
    model_version: str = "week9-insight-generator-0.1",
) -> GeneratedInsight:
    return GeneratedInsight(
        insight_id=insight_id,
        query=query,
        insight_text=insight_text,
        insight_type=insight_type,
        evidence_citations=evidence_citations if evidence_citations is not None else ["Incident abc123 | severity=High"],
        actionable_steps=actionable_steps if actionable_steps is not None else [
            "Anaesthesiologist documents plan before induction",
            "Nurse prepares backup equipment on first failure",
        ],
        confidence=confidence,
        specificity_score=specificity_score,
        generated_at=generated_at,
        model_version=model_version,
    )


def _make_batch(insights: list[GeneratedInsight] | None = None) -> InsightBatch:
    items = insights if insights is not None else [_make_insight()]
    return InsightBatch(
        query="test query",
        insights=items,
        total=len(items),
        generation_confidence="High",
        evidence_count=len(items),
        model_version="week9-insight-generator-0.1",
    )


# ---------------------------------------------------------------------------
# InsightItem validation
# ---------------------------------------------------------------------------


class TestInsightItemValidation:
    def test_valid_item_accepted(self):
        item = InsightItem(
            insight_text="This is a specific clinical finding referencing Incident abc123.",
            insight_type="root_cause",
            evidence_citations=["Incident abc123 | severity=High"],
            actionable_steps=["Anaesthesiologist documents plan B"],
            confidence="High",
        )
        assert item.insight_type == "root_cause"
        assert item.confidence == "High"

    def test_short_insight_text_rejected(self):
        with pytest.raises(ValidationError):
            InsightItem(
                insight_text="Too short.",
                insight_type="general",
                confidence="Low",
            )

    def test_insight_type_normalised_to_lowercase(self):
        item = InsightItem(
            insight_text="A sufficiently long insight text about clinical safety patterns.",
            insight_type="PATTERN_ANALYSIS",
            confidence="Moderate",
        )
        assert item.insight_type == "pattern_analysis"

    def test_insight_type_with_spaces_normalised(self):
        item = InsightItem(
            insight_text="A sufficiently long insight text about clinical safety patterns.",
            insight_type="safety recommendations",
            confidence="Low",
        )
        assert item.insight_type == "safety_recommendations"

    def test_unknown_insight_type_defaults_to_general(self):
        item = InsightItem(
            insight_text="A sufficiently long insight text about clinical safety patterns.",
            insight_type="completely_invalid_type",
            confidence="Low",
        )
        assert item.insight_type == "general"

    def test_confidence_normalised_to_title_case(self):
        item = InsightItem(
            insight_text="A sufficiently long insight text about clinical safety patterns.",
            insight_type="general",
            confidence="high",
        )
        assert item.confidence == "High"

    def test_invalid_confidence_defaults_to_low(self):
        item = InsightItem(
            insight_text="A sufficiently long insight text about clinical safety patterns.",
            insight_type="general",
            confidence="uncertain",
        )
        assert item.confidence == "Low"

    def test_default_empty_lists(self):
        item = InsightItem(
            insight_text="A sufficiently long insight text about clinical safety patterns.",
            insight_type="general",
            confidence="Low",
        )
        assert item.evidence_citations == []
        assert item.actionable_steps == []

    def test_extra_fields_ignored(self):
        item = InsightItem(
            insight_text="A sufficiently long insight text about clinical safety patterns.",
            insight_type="general",
            confidence="Low",
            unknown_extra_field="should be ignored",
        )
        assert not hasattr(item, "unknown_extra_field")


# ---------------------------------------------------------------------------
# InsightLLMResponse validation
# ---------------------------------------------------------------------------


class TestInsightLLMResponse:
    def test_valid_response_accepted(self):
        resp = InsightLLMResponse(
            insights=[
                InsightItem(
                    insight_text="Three incidents share a pattern of delayed escalation to video laryngoscopy.",
                    insight_type="pattern_analysis",
                    evidence_citations=["Incident abc123 | severity=High"],
                    actionable_steps=["Step 1", "Step 2"],
                    confidence="High",
                )
            ]
        )
        assert resp.insights[0].confidence == "High"

    def test_empty_insights_list_rejected(self):
        with pytest.raises(ValidationError):
            InsightLLMResponse(insights=[])

    def test_multiple_insights_accepted(self):
        items = [
            InsightItem(
                insight_text=f"Insight {i}: specific clinical finding about the pattern observed.",
                insight_type="general",
                confidence="Moderate",
            )
            for i in range(3)
        ]
        resp = InsightLLMResponse(insights=items)
        assert len(resp.insights) == 3


# ---------------------------------------------------------------------------
# GeneratedInsight properties
# ---------------------------------------------------------------------------


class TestGeneratedInsightProperties:
    def test_is_grounded_true_when_citations_present(self):
        insight = _make_insight(evidence_citations=["Incident abc123 | severity=High"])
        assert insight.is_grounded is True

    def test_is_grounded_false_when_no_citations(self):
        insight = _make_insight(evidence_citations=[])
        assert insight.is_grounded is False

    def test_is_actionable_true_when_two_or_more_steps(self):
        insight = _make_insight(actionable_steps=["Step 1", "Step 2"])
        assert insight.is_actionable is True

    def test_is_actionable_true_with_three_steps(self):
        insight = _make_insight(actionable_steps=["Step 1", "Step 2", "Step 3"])
        assert insight.is_actionable is True

    def test_is_actionable_false_with_one_step(self):
        insight = _make_insight(actionable_steps=["Only one step"])
        assert insight.is_actionable is False

    def test_is_actionable_false_with_no_steps(self):
        insight = _make_insight(actionable_steps=[])
        assert insight.is_actionable is False


# ---------------------------------------------------------------------------
# InsightBatch properties
# ---------------------------------------------------------------------------


class TestInsightBatchProperties:
    def test_all_citations_deduplicates_across_insights(self):
        shared_citation = "Incident abc123 | severity=High"
        i1 = _make_insight("id1", evidence_citations=[shared_citation, "Incident xyz | severity=Low"])
        i2 = _make_insight("id2", evidence_citations=[shared_citation, "Incident zzz | severity=High"])
        batch = _make_batch([i1, i2])
        citations = batch.all_citations
        assert len(citations) == 3
        assert citations.count(shared_citation) == 1

    def test_all_citations_preserves_order(self):
        i1 = _make_insight("id1", evidence_citations=["Incident A", "Incident B"])
        i2 = _make_insight("id2", evidence_citations=["Incident C"])
        batch = _make_batch([i1, i2])
        assert batch.all_citations == ["Incident A", "Incident B", "Incident C"]

    def test_all_citations_empty_when_no_citations(self):
        i1 = _make_insight("id1", evidence_citations=[])
        batch = _make_batch([i1])
        assert batch.all_citations == []

    def test_grounded_count_correct(self):
        grounded = _make_insight("id1", evidence_citations=["Incident A"])
        ungrounded = _make_insight("id2", evidence_citations=[])
        batch = _make_batch([grounded, ungrounded, grounded])
        assert batch.grounded_count == 2

    def test_actionable_count_correct(self):
        actionable = _make_insight("id1", actionable_steps=["Step 1", "Step 2"])
        not_actionable = _make_insight("id2", actionable_steps=["Only step"])
        batch = _make_batch([actionable, not_actionable])
        assert batch.actionable_count == 1

    def test_empty_batch_properties(self):
        batch = InsightBatch(
            query="q",
            insights=[],
            total=0,
            generation_confidence="Low",
            evidence_count=0,
            model_version="v0",
        )
        assert batch.all_citations == []
        assert batch.grounded_count == 0
        assert batch.actionable_count == 0
