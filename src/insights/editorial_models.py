"""Data models for Week 10 Editorial Intelligence Layer.

Two layers:
  - Pydantic models (SectionLLMItem, EditorialLLMResponse, IncidentEditorialLLMResponse):
    structured output contracts for the LLM; validated on receipt.
  - Dataclasses (EditorialSection, EditorialReport, APSAArticle): processed,
    quality-annotated representations for API responses and downstream consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# LLM structured-output contract
# ---------------------------------------------------------------------------


class SectionLLMItem(BaseModel):
    """One editorial section as returned by the LLM."""

    model_config = {"extra": "ignore"}

    theme: str = Field(
        ...,
        description="root_cause | pattern_analysis | safety_recommendations | general",
    )
    title: str = Field(..., min_length=5, description="Short section heading (4-8 words)")
    narrative: str = Field(
        ...,
        min_length=50,
        description="APSA-style prose paragraph (no bullet points, no headers)",
    )
    key_learning: str = Field(
        ...,
        min_length=10,
        description="One concise sentence capturing the essential safety message",
    )

    @field_validator("theme", mode="before")
    @classmethod
    def normalise_theme(cls, v: str) -> str:
        normalised = str(v).lower().strip().replace(" ", "_")
        valid = {"root_cause", "pattern_analysis", "safety_recommendations", "general"}
        return normalised if normalised in valid else "general"


class EditorialLLMResponse(BaseModel):
    """Top-level structured output contract for the editorial LLM call."""

    model_config = {"extra": "ignore"}

    evocative_title: str = Field(
        "",
        description="Journalistic headline in ALL CAPS with subtitle, e.g. 'PATTERNS IN SILENCE: THE QUIET RECURRENCE OF AIRWAY EVENTS'",
    )
    executive_summary: str = Field(
        ...,
        min_length=30,
        description="Case vignette or 2-3 sentence clinical narrative overview — what happened, what was found",
    )
    sections: list[SectionLLMItem] = Field(..., min_length=1)
    conclusion: str = Field(
        ...,
        min_length=30,
        description="Closing reflection paragraph with call to action",
    )
    clinical_references: list[str] = Field(
        default_factory=list,
        description="4-6 real academic citations in Vancouver format: 'Author A, Author B. Title. Journal. Year;Vol(Issue):Pages.'",
    )


class IncidentEditorialLLMResponse(BaseModel):
    """Structured output contract for per-incident APSA newsletter article generation."""

    model_config = {"extra": "ignore"}

    evocative_title: str = Field(
        ...,
        min_length=10,
        description="Journalistic headline in ALL CAPS with subtitle",
    )
    vignette: str = Field(
        ...,
        min_length=30,
        description="2-3 sentence anonymous case description of what happened",
    )
    body_paragraphs: list[str] = Field(
        ...,
        min_length=3,
        description="3-5 educational paragraphs about the broader clinical topic",
    )
    clinical_references: list[str] = Field(
        ...,
        min_length=1,
        description="4-6 real academic citations in Vancouver format",
    )


# ---------------------------------------------------------------------------
# Processed output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EditorialSection:
    """A single themed section of the editorial report."""

    section_id: str
    theme: str                    # root_cause | pattern_analysis | safety_recommendations | general
    title: str                    # "Root Cause Analysis"
    narrative: str                # APSA-style prose
    supporting_insights: list     # list[GeneratedInsight] — typed as Any to avoid circular
    evidence_citations: list[str] # deduplicated citations from supporting insights
    key_learning: str             # one-sentence distillation
    tone_score: float             # 0.0-1.0; 1.0 = no forbidden phrases
    generated_at: str
    model_version: str

    @property
    def insight_count(self) -> int:
        """Number of insights backing this section."""
        return len(self.supporting_insights)

    @property
    def is_grounded(self) -> bool:
        """True when at least one evidence citation is present."""
        return len(self.evidence_citations) > 0

    @property
    def word_count(self) -> int:
        """Approximate word count of the narrative."""
        return len(self.narrative.split())


@dataclass
class EditorialReport:
    """A complete APSA-style editorial report generated from an InsightBatch."""

    report_id: str
    query: str
    title: str
    executive_summary: str
    sections: list[EditorialSection]
    conclusion: str
    total_incidents_referenced: int  # unique incident citations across all sections
    all_citations: list[str]         # deduplicated, insertion-ordered
    tone_score: float                # overall 0.0-1.0 tone quality score
    has_llm_narrative: bool          # False when in deterministic fallback mode
    generated_at: str
    model_version: str
    # APSA format additions — optional so existing construction stays backward-compatible
    evocative_title: str = ""
    clinical_references: list[str] = field(default_factory=list)

    @property
    def section_count(self) -> int:
        """Number of editorial sections."""
        return len(self.sections)

    @property
    def word_count(self) -> int:
        """Total word count across executive summary, all narratives, and conclusion."""
        parts = [self.executive_summary, self.conclusion]
        parts += [s.narrative for s in self.sections]
        return sum(len(p.split()) for p in parts)

    @property
    def grounded_section_count(self) -> int:
        """Number of sections with at least one evidence citation."""
        return sum(1 for s in self.sections if s.is_grounded)


@dataclass
class APSAArticle:
    """A single APSA-style educational article generated from one incident."""

    article_id: str
    incident_id: str
    title: str          # evocative journalistic headline
    vignette: str       # anonymous case description (2-3 sentences)
    body: str           # educational prose (joined body_paragraphs)
    clinical_references: list[str]
    incident_metadata: dict
    generated_at: str
    model_version: str = "week12-newsletter-0.1"
