"""Rule-based severity analysis for Week 3 scaffolding.

The current implementation is deterministic and can be swapped later with a
model-driven analyzer while preserving the same result shape.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.models.incident import Incident
from src.normalization.enums import SeverityLevel


@dataclass(frozen=True)
class SeverityResult:
    """Severity assessment output."""

    severity: str
    score: float
    rationale: str


CRITICAL_HINTS = ("cardiac arrest", "cpR", "code blue", "death", "life-threatening")
HIGH_HINTS = ("insufflator", "malfunction", "surgery not done", "wrong site", "blood loss", "reoperation")
MODERATE_HINTS = ("delay", "repeat", "extra monitoring", "minor injury", "near miss")


class SeverityAnalyzer:
    """Estimate severity from incident content and outcome fields."""

    def analyze_text(self, text: str | None) -> SeverityResult:
        combined = (text or "").strip().lower()

        if any(hint.lower() in combined for hint in CRITICAL_HINTS):
            return SeverityResult(SeverityLevel.CRITICAL.value, 0.95, "Critical harm indicators found")

        if any(hint.lower() in combined for hint in HIGH_HINTS):
            return SeverityResult(SeverityLevel.HIGH.value, 0.8, "High-severity operational impact detected")

        if any(hint.lower() in combined for hint in MODERATE_HINTS):
            return SeverityResult(SeverityLevel.MODERATE.value, 0.6, "Moderate impact or near-miss indicators found")

        return SeverityResult(SeverityLevel.LOW.value, 0.35, "No strong escalation indicators found")

    def analyze_incident(self, incident: Incident) -> SeverityResult:
        """Analyze severity using all available textual incident fields."""
        fields = [
            incident.incident.incident_description,
            incident.incident.incident_details,
            incident.outcome.patient_safety,
            incident.outcome.morbidity,
            incident.outcome.personnel_safety,
            incident.outcome.patient_satisfaction,
        ]
        text = " ".join(part.strip() for part in fields if part)
        result = self.analyze_text(text)

        # Escalate if the outcome explicitly says surgery was not done.
        if incident.outcome.patient_safety and "surgery not done" in incident.outcome.patient_safety.lower():
            return SeverityResult(SeverityLevel.HIGH.value, max(result.score, 0.8), "Patient safety impact aborted surgery")

        return result
