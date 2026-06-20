"""Unit tests for Week 10 editorial data models.

Covers:
  - SectionLLMItem validation and theme normalisation
  - EditorialLLMResponse validation
  - EditorialSection property accessors (insight_count, is_grounded, word_count)
  - EditorialReport computed properties (section_count, word_count, grounded_section_count)
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.insights.editorial_models import (
    EditorialLLMResponse,
    EditorialReport,
    EditorialSection,
    SectionLLMItem,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_section(
    section_id: str = "sec-001",
    theme: str = "pattern_analysis",
    title: str = "Pattern Observations",
    narrative: str = (
        "Analysis of the retrieved incidents reveals a consistent gap between "
        "equipment availability and operational readiness in difficult airway scenarios. "
        "Three cases demonstrate that pre-positioning protocols represent the highest-yield "
        "intervention, not further equipment procurement."
    ),
    evidence_citations: list[str] | None = None,
    key_learning: str = "Pre-positioning video laryngoscopy reduces escalation delay.",
    tone_score: float = 1.0,
    supporting_insights: list | None = None,
) -> EditorialSection:
    return EditorialSection(
        section_id=section_id,
        theme=theme,
        title=title,
        narrative=narrative,
        supporting_insights=supporting_insights or [],
        evidence_citations=evidence_citations
        if evidence_citations is not None
        else ["Incident abc123 | severity=High"],
        key_learning=key_learning,
        tone_score=tone_score,
        generated_at="2026-06-13T00:00:00+00:00",
        model_version="week10-editorial-engine-0.1",
    )


def _make_report(sections: list[EditorialSection] | None = None) -> EditorialReport:
    items = sections if sections is not None else [_make_section()]
    return EditorialReport(
        report_id="rep-001",
        query="difficult airway patterns",
        title="Clinical Safety Analysis: difficult airway patterns",
        executive_summary=(
            "Analysis of five incidents identified two thematic areas requiring attention: "
            "airway device pre-positioning and escalation timing."
        ),
        sections=items,
        conclusion=(
            "The themes identified in this analysis warrant review at the next clinical "
            "governance meeting. Systemic pre-positioning protocols offer the highest-yield "
            "improvement opportunity."
        ),
        total_incidents_referenced=3,
        all_citations=["Incident abc123 | severity=High"],
        tone_score=1.0,
        has_llm_narrative=True,
        generated_at="2026-06-13T00:00:00+00:00",
        model_version="week10-editorial-engine-0.1",
    )


# ---------------------------------------------------------------------------
# SectionLLMItem validation
# ---------------------------------------------------------------------------


class TestSectionLLMItemValidation:
    def test_valid_item_accepted(self):
        item = SectionLLMItem(
            theme="root_cause",
            title="Systemic Airway Preparation Gaps",
            narrative=(
                "A consistent pattern emerges across the retrieved incidents involving "
                "unanticipated difficult airways. Pre-induction planning documentation "
                "was absent in all three cases, suggesting a systemic gap in the "
                "pre-anaesthetic briefing process."
            ),
            key_learning="Mandatory pre-induction Plan A/B documentation reduces escalation delay.",
        )
        assert item.theme == "root_cause"

    def test_short_title_rejected(self):
        with pytest.raises(ValidationError):
            SectionLLMItem(
                theme="general",
                title="Hi",
                narrative="A" * 60,
                key_learning="Key message here.",
            )

    def test_short_narrative_rejected(self):
        with pytest.raises(ValidationError):
            SectionLLMItem(
                theme="general",
                title="Valid Title Here",
                narrative="Too short.",
                key_learning="Key message here.",
            )

    def test_theme_normalised_to_lowercase(self):
        item = SectionLLMItem(
            theme="PATTERN_ANALYSIS",
            title="Pattern Observations Section",
            narrative="A" * 60,
            key_learning="Key message here.",
        )
        assert item.theme == "pattern_analysis"

    def test_theme_with_spaces_normalised(self):
        item = SectionLLMItem(
            theme="safety recommendations",
            title="Safety Recommendations",
            narrative="A" * 60,
            key_learning="Key message here.",
        )
        assert item.theme == "safety_recommendations"

    def test_invalid_theme_defaults_to_general(self):
        item = SectionLLMItem(
            theme="completely_invalid",
            title="Valid Title Here",
            narrative="A" * 60,
            key_learning="Key message here.",
        )
        assert item.theme == "general"

    def test_extra_fields_ignored(self):
        item = SectionLLMItem(
            theme="general",
            title="Valid Section Title",
            narrative="A" * 60,
            key_learning="Key message here.",
            unknown_field="ignored",
        )
        assert not hasattr(item, "unknown_field")


# ---------------------------------------------------------------------------
# EditorialLLMResponse validation
# ---------------------------------------------------------------------------


class TestEditorialLLMResponse:
    def _valid_section(self) -> dict:
        return {
            "theme": "pattern_analysis",
            "title": "Pattern Observations Section",
            "narrative": "A" * 60,
            "key_learning": "Key message here.",
        }

    def test_valid_response_accepted(self):
        resp = EditorialLLMResponse(
            executive_summary="Two themes identified across five anaesthesia incidents.",
            sections=[SectionLLMItem(**self._valid_section())],
            conclusion="These findings warrant review at the next clinical governance meeting.",
        )
        assert len(resp.sections) == 1

    def test_empty_sections_rejected(self):
        with pytest.raises(ValidationError):
            EditorialLLMResponse(
                executive_summary="Summary here.",
                sections=[],
                conclusion="Conclusion here.",
            )

    def test_short_executive_summary_rejected(self):
        with pytest.raises(ValidationError):
            EditorialLLMResponse(
                executive_summary="Too short.",
                sections=[SectionLLMItem(**self._valid_section())],
                conclusion="Conclusion here with enough text.",
            )

    def test_multiple_sections_accepted(self):
        sections = [SectionLLMItem(**self._valid_section()) for _ in range(3)]
        resp = EditorialLLMResponse(
            executive_summary="Multiple themes identified across the retrieved incident set.",
            sections=sections,
            conclusion="These findings warrant review at the next governance meeting.",
        )
        assert len(resp.sections) == 3


# ---------------------------------------------------------------------------
# EditorialSection properties
# ---------------------------------------------------------------------------


class TestEditorialSectionProperties:
    def test_insight_count_correct(self):
        section = _make_section(supporting_insights=["a", "b", "c"])
        assert section.insight_count == 3

    def test_insight_count_zero_when_empty(self):
        section = _make_section(supporting_insights=[])
        assert section.insight_count == 0

    def test_is_grounded_true_when_citations_present(self):
        section = _make_section(evidence_citations=["Incident abc123 | severity=High"])
        assert section.is_grounded is True

    def test_is_grounded_false_when_no_citations(self):
        section = _make_section(evidence_citations=[])
        assert section.is_grounded is False

    def test_word_count_approximate(self):
        narrative = "This is a six word narrative."
        section = _make_section(narrative=narrative)
        assert section.word_count == 6


# ---------------------------------------------------------------------------
# EditorialReport properties
# ---------------------------------------------------------------------------


class TestEditorialReportProperties:
    def test_section_count(self):
        report = _make_report([_make_section("s1"), _make_section("s2")])
        assert report.section_count == 2

    def test_section_count_zero_when_empty(self):
        report = _make_report([])
        assert report.section_count == 0

    def test_word_count_includes_summary_and_conclusion(self):
        report = _make_report([])
        # executive_summary + conclusion words
        expected = len(report.executive_summary.split()) + len(report.conclusion.split())
        assert report.word_count == expected

    def test_word_count_includes_all_section_narratives(self):
        s1 = _make_section("s1", narrative="One two three four five.")
        s2 = _make_section("s2", narrative="Six seven eight.")
        report = _make_report([s1, s2])
        base = len(report.executive_summary.split()) + len(report.conclusion.split())
        assert report.word_count == base + 5 + 3

    def test_grounded_section_count_correct(self):
        grounded = _make_section("s1", evidence_citations=["Incident A"])
        ungrounded = _make_section("s2", evidence_citations=[])
        report = _make_report([grounded, ungrounded])
        assert report.grounded_section_count == 1

    def test_grounded_section_count_zero_when_all_ungrounded(self):
        sections = [_make_section(f"s{i}", evidence_citations=[]) for i in range(3)]
        report = _make_report(sections)
        assert report.grounded_section_count == 0

    def test_all_citations_on_report_are_set_at_init(self):
        report = _make_report()
        assert "Incident abc123 | severity=High" in report.all_citations
