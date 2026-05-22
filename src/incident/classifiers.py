"""Rule-based incident type classification for Week 3 scaffolding.

This module provides a deterministic multi-label classifier that can later be
replaced or augmented by LLM-based classification.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from src.models.incident import Incident
from src.normalization.enums import IncidentType


INCIDENT_CLASSIFICATION_RULES: list[tuple[str, tuple[str, ...]]] = [
    (IncidentType.MEDICATION.value, ("medication", "drug error", "dose error", "wrong drug")),
    (IncidentType.EQUIPMENT.value, ("equipment", "insufflator", "device", "malfunction", "failure")),
    (IncidentType.COMMUNICATION.value, ("communication", "handover", "handoff", "miscommunication")),
    (IncidentType.AIRWAY.value, ("airway", "intubation", "ventilation", "extubation", "ett")),
    (IncidentType.RESPIRATORY.value, ("respiratory", "desaturation", "hypoxia", "bronchospasm")),
    (
        IncidentType.CARDIOVASCULAR.value,
        ("cardiac", "cardiovascular", "arrhythmia", "arrest", "hypotension", "bleeding", "shock"),
    ),
    (IncidentType.PROCEDURE.value, ("wrong site", "site not verified", "procedure", "incision", "checklist")),
    (IncidentType.POSITIONING.value, ("positioning", "pressure injury", "nerve injury", "padding")),
    (IncidentType.DOCUMENTATION.value, ("documentation", "chart", "record", "form", "entry")),
]


@dataclass(frozen=True)
class ClassificationResult:
    """Multi-label classification result."""

    labels: list[str]
    confidence: float
    matched_keywords: list[str]


class IncidentTypeClassifier:
    """Classify incidents into a canonical multi-label taxonomy."""

    def classify_text(self, text: str | None) -> ClassificationResult:
        combined = (text or "").strip().lower()
        labels: list[str] = []
        matched_keywords: list[str] = []

        for label, keywords in INCIDENT_CLASSIFICATION_RULES:
            if any(keyword in combined for keyword in keywords):
                labels.append(label)
                matched_keywords.extend([keyword for keyword in keywords if keyword in combined])

        labels = unique_labels(labels)

        if not labels:
            labels = [IncidentType.OTHER.value]

        confidence = min(0.55 + (0.08 * len(labels)), 0.95)
        if IncidentType.OTHER.value in labels:
            confidence = 0.35

        return ClassificationResult(labels=labels, confidence=confidence, matched_keywords=matched_keywords)

    def classify_incident(self, incident: Incident) -> ClassificationResult:
        """Classify an Incident from all available textual fields."""
        fields = [
            incident.incident.incident_description,
            incident.incident.incident_details,
            incident.incident.incident_detection,
            incident.surgery.procedure,
            incident.surgery.surgical_branch,
            incident.outcome.patient_safety,
            incident.outcome.morbidity,
        ]
        text = " ".join(part.strip() for part in fields if part)
        return self.classify_text(text)


def unique_labels(labels: Iterable[str]) -> list[str]:
    """Preserve order while removing duplicates."""
    seen: set[str] = set()
    ordered: list[str] = []
    for label in labels:
        if label not in seen:
            seen.add(label)
            ordered.append(label)
    return ordered
