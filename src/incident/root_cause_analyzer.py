"""Deterministic root cause analysis for clinical incidents."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.models.incident import Incident

class RootCauseAnalysis(BaseModel):
    """Structured RCA output used by the understanding pipeline."""

    root_cause: str = Field(..., description="Grounded root cause statement")
    contributing_factors: list[str] = Field(default_factory=list, description="Grounded contributing factors")
    contributing_factor_categories: list[str] = Field(
        default_factory=list, description="Canonical contributing factor categories"
    )
    key_learning: str = Field(..., description="Preventive learning derived from the incident")
    preventive_recommendations: list[str] = Field(default_factory=list, description="Preventive recommendations")
    systemic_failure_detected: bool = Field(..., description="Whether a systemic failure pattern was detected")
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in the RCA output")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_content(self) -> "RootCauseAnalysis":
        if not self.root_cause.strip():
            raise ValueError("root_cause must not be empty")
        if not self.key_learning.strip():
            raise ValueError("key_learning must not be empty")
        return self


@dataclass(slots=True)
class RootCauseAnalyzer:
    """Deterministic RCA helper for Week 4.

    The logic intentionally stays grounded in the incident text and known
    taxonomy labels so it does not invent unsupported causes.
    """

    def analyze_incident(
        self,
        incident: Incident,
        incident_types: list[str] | None = None,
        severity: str | None = None,
    ) -> RootCauseAnalysis:
        incident_types = incident_types or []
        text = self._incident_text(incident)
        matched_label, root_cause = self._detect_primary_signal(text)
        systemic_failure_detected = matched_label is not None

        categories = self._derive_categories(incident_types, matched_label)
        contributing_factors = self._derive_contributing_factors(incident, categories, text)
        key_learning = self._derive_key_learning(incident_types, severity, matched_label, systemic_failure_detected)
        recommendations = self._derive_recommendations(categories, systemic_failure_detected)

        confidence_score = 0.92 if systemic_failure_detected else 0.62

        return RootCauseAnalysis(
            root_cause=root_cause,
            contributing_factors=contributing_factors,
            contributing_factor_categories=categories,
            key_learning=key_learning,
            preventive_recommendations=recommendations,
            systemic_failure_detected=systemic_failure_detected,
            confidence_score=confidence_score,
        )

    def detect_systemic_failure(self, incident: Incident) -> bool:
        text = self._incident_text(incident)
        matched_label, _ = self._detect_primary_signal(text)
        return matched_label is not None

    def _incident_text(self, incident: Incident) -> str:
        return " ".join(
            part.strip()
            for part in [
                incident.patient.age_range,
                incident.surgery.type_of_procedure,
                incident.surgery.surgical_branch,
                incident.surgery.procedure,
                incident.incident.incident_description,
                incident.incident.incident_details,
                incident.incident.time_of_incident,
                incident.incident.place_of_incident,
                incident.incident.timing_of_event,
                incident.incident.incident_detection,
                incident.anesthesia.primary_technique,
                incident.anesthesia.intubation_type,
                incident.outcome.patient_safety,
                incident.outcome.morbidity,
                incident.outcome.harm_severity,
            ]
            if part
        ).lower()

    def _detect_primary_signal(self, text: str) -> tuple[str | None, str]:
        signal_map = [
            ("equipment failure", "equipment", "malfunction", "insufflator", "device"),
            ("procedure-related", "wrong site", "site not verified", "procedure verification", "site marking"),
            ("communication failure", "communication", "handoff", "escalation", "coordination"),
            ("medication error", "medication", "drug", "dose", "labeling"),
            ("airway event", "airway", "intubation", "ett", "laryngospasm"),
            ("respiratory event", "respiratory", "oxygen", "hypoxia", "capnograph"),
        ]

        for category, *keywords in signal_map:
            if any(keyword in text for keyword in keywords):
                return category.title(), self._root_cause_for_category(category)

        return None, "Insufficient detail for definitive root cause; manual review recommended"

    def _root_cause_for_category(self, category: str) -> str:
        mapping = {
            "equipment failure": "Equipment reliability or pre-use verification gap",
            "procedure-related": "Procedure verification or site marking gap",
            "communication failure": "Communication or handoff process gap",
            "medication error": "Medication identification or administration process gap",
            "airway event": "Airway management or device setup gap",
            "respiratory event": "Respiratory monitoring or escalation gap",
        }
        return mapping.get(category, "Insufficient detail for definitive root cause; manual review recommended")

    def _derive_categories(self, incident_types: list[str], matched_label: str | None) -> list[str]:
        categories = list(incident_types)
        if matched_label:
            categories.append(matched_label)
        return self._unique(categories)

    def _derive_contributing_factors(self, incident: Incident, categories: list[str], text: str) -> list[str]:
        factors: list[str] = []
        if incident.surgery.type_of_procedure:
            factors.append(f"Procedure type: {incident.surgery.type_of_procedure}")
        if incident.surgery.surgical_branch:
            factors.append(f"Surgical branch: {incident.surgery.surgical_branch}")
        if incident.anesthesia.primary_technique:
            factors.append(f"Anesthesia technique: {incident.anesthesia.primary_technique}")

        for category in categories:
            factors.append(f"Classification signal: {category}")

        if "equipment" in text:
            factors.append("Equipment readiness or verification gap")
        if "communication" in text or "handoff" in text:
            factors.append("Team communication or handoff gap")
        if "label" in text or "medication" in text:
            factors.append("Labeling or medication identification gap")
        if not factors:
            factors.append("Insufficient detail for definitive contributing factors; manual review recommended")
        return self._unique(factors)

    def _derive_key_learning(
        self,
        incident_types: list[str],
        severity: str | None,
        matched_label: str | None,
        systemic_failure_detected: bool,
    ) -> str:
        if severity in {"High", "Critical"}:
            return "Reinforce pre-procedure verification, escalation, and team communication before high-risk events."
        if matched_label == "Communication Failure" or "Communication Failure" in incident_types:
            return "Standardize handoff and escalation communication to reduce avoidable variation."
        if matched_label == "Equipment Failure" or "Equipment Failure" in incident_types:
            return "Use structured equipment checks and escalation pathways before induction or procedure start."
        if systemic_failure_detected:
            return "Document the event clearly and review local process gaps for prevention."
        return "Document the event clearly and review local process gaps for prevention."

    def _derive_recommendations(self, categories: list[str], systemic_failure_detected: bool) -> list[str]:
        recommendations = [
            "Strengthen pre-event verification steps.",
            "Document escalation criteria and responsibilities.",
        ]
        if systemic_failure_detected:
            recommendations.append("Review local process controls and escalation pathways.")
        if "Equipment Failure" in categories:
            recommendations.append("Add equipment readiness checks before procedure start.")
        if "Communication Failure" in categories:
            recommendations.append("Use closed-loop communication during critical transitions.")
        if "Procedure-Related" in categories:
            recommendations.append("Confirm site, side, and procedure before incision.")
        return self._unique(recommendations)

    def _unique(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(values))
