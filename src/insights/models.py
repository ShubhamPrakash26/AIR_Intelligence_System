"""Data models for Week 9 Insight Generation.

Two layers:
  - Pydantic models (InsightItem, InsightLLMResponse): structured output contract
    for the LLM; validated on receipt.
  - Dataclasses (GeneratedInsight, InsightBatch): processed, quality-annotated
    representations for API responses and downstream consumers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# LLM structured-output contract
# ---------------------------------------------------------------------------


class InsightItem(BaseModel):
    """Single insight as returned by the LLM via with_structured_output."""

    model_config = {"extra": "ignore"}

    insight_text: str = Field(..., min_length=20)
    insight_type: str = Field(
        ...,
        description="root_cause | pattern_analysis | safety_recommendations | general",
    )
    evidence_citations: list[str] = Field(default_factory=list)
    actionable_steps: list[str] = Field(default_factory=list)
    confidence: str = Field(..., description="High | Moderate | Low")

    @field_validator("insight_type", mode="before")
    @classmethod
    def normalise_insight_type(cls, v: str) -> str:
        normalised = str(v).lower().strip().replace(" ", "_")
        valid = {"root_cause", "pattern_analysis", "safety_recommendations", "general"}
        return normalised if normalised in valid else "general"

    @field_validator("confidence", mode="before")
    @classmethod
    def normalise_confidence(cls, v: str) -> str:
        title = str(v).strip().title()
        return title if title in ("High", "Moderate", "Low") else "Low"


class InsightLLMResponse(BaseModel):
    """Top-level structured output contract for the insight LLM call."""

    model_config = {"extra": "ignore"}

    insights: list[InsightItem] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Processed output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class GeneratedInsight:
    """A fully processed insight with quality metrics."""

    insight_id: str
    query: str
    insight_text: str
    insight_type: str
    evidence_citations: list[str]
    actionable_steps: list[str]
    confidence: str
    specificity_score: float  # 0.0-1.0 derived from citations + actions + text length
    generated_at: str         # ISO-8601 UTC timestamp
    model_version: str

    @property
    def is_grounded(self) -> bool:
        """True when at least one evidence citation is present."""
        return len(self.evidence_citations) > 0

    @property
    def is_actionable(self) -> bool:
        """True when at least two actionable steps are present."""
        return len(self.actionable_steps) >= 2


@dataclass
class InsightBatch:
    """Collection of insights generated for a single query."""

    query: str
    insights: list[GeneratedInsight]
    total: int
    generation_confidence: str   # batch-level rollup: High | Moderate | Low
    evidence_count: int          # unique incident citations across all insights
    model_version: str

    @property
    def all_citations(self) -> list[str]:
        """Deduplicated list of every citation referenced across all insights."""
        seen: set[str] = set()
        result: list[str] = []
        for ins in self.insights:
            for c in ins.evidence_citations:
                if c not in seen:
                    seen.add(c)
                    result.append(c)
        return result

    @property
    def grounded_count(self) -> int:
        """Number of insights that reference at least one evidence citation."""
        return sum(1 for i in self.insights if i.is_grounded)

    @property
    def actionable_count(self) -> int:
        """Number of insights with two or more actionable steps."""
        return sum(1 for i in self.insights if i.is_actionable)
