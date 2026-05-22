from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from src.models.analysis import AIAnalysis
from src.models.incident import Incident
from src.utils.config import settings
from src.validation.schemas import (
    ValidationAttempt,
    ValidationOutputConstraints,
    ValidationReport,
    ValidationResult,
)


_HIGH_RISK_OUTCOME_MARKERS = (
    "cardiac arrest",
    "death",
    "died",
    "fatal",
    "anesthetic delivered - surgery not done",
)


@dataclass(slots=True)
class ValidationAgent:
    """Rule-based validation for incident analyses.

    This is intentionally deterministic so Week 4 validation can run offline,
    and later act as a guardrail before storing or sending outputs downstream.
    """

    confidence_threshold: float = settings.confidence_threshold
    output_constraints: ValidationOutputConstraints = field(default_factory=ValidationOutputConstraints)

    def _build_result(self, status: str, errors: list[str], warnings: list[str]) -> ValidationResult:
        return ValidationResult(status=status, errors=errors, warnings=warnings)

    def validate(self, incident: Incident, analysis: AIAnalysis) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []

        if analysis.validation_status not in self.output_constraints.allowed_statuses:
            errors.append("validation_status is not permitted")

        for field_name in self.output_constraints.required_nonempty_fields:
            value = getattr(analysis, field_name, None)
            if isinstance(value, list):
                if not value:
                    errors.append(f"{field_name} is required")
            elif not str(value or "").strip():
                errors.append(f"{field_name} is required")

        incident_text = " ".join(
            filter(
                None,
                [
                    incident.incident.incident_description,
                    incident.outcome.patient_safety,
                    incident.outcome.morbidity,
                    incident.outcome.harm_severity,
                ],
            )
        ).lower()

        if analysis.severity.lower() == "low" and any(marker in incident_text for marker in _HIGH_RISK_OUTCOME_MARKERS):
            errors.append("severity=Low conflicts with high-risk outcome signals")

        if analysis.severity.lower() in {"high", "critical"} and len(analysis.key_learning.strip()) < 10:
            errors.append("high-severity incidents require a substantive key_learning")

        if analysis.confidence_score < self.confidence_threshold:
            warnings.append(
                f"confidence_score below threshold ({analysis.confidence_score:.2f} < {self.confidence_threshold:.2f})"
            )

        if errors:
            errors = errors[: self.output_constraints.max_error_count]
            status = "invalid"
        elif warnings:
            status = "needs_review"
        else:
            status = "valid"

        return self._build_result(status=status, errors=errors, warnings=warnings)

    def retry_validate(
        self,
        incident: Incident,
        analysis: AIAnalysis,
        *,
        repair_fn: Callable[[Incident, AIAnalysis, ValidationResult, int], AIAnalysis] | None = None,
        max_attempts: int | None = None,
    ) -> ValidationReport:
        """Validate an analysis with optional repair retries.

        The repair callback can adjust the analysis between attempts. If no callback
        is provided, the method records the first validation attempt and returns it.
        """

        max_attempts = max_attempts or settings.validation_retries
        max_attempts = max(1, max_attempts)

        attempts: list[ValidationAttempt] = []
        current_analysis = analysis

        for attempt_number in range(1, max_attempts + 1):
            result = self.validate(incident, current_analysis)
            attempts.append(ValidationAttempt(attempt_number=attempt_number, result=result))

            if result.status == "valid":
                break

            if repair_fn is None or attempt_number >= max_attempts:
                break

            current_analysis = repair_fn(incident, current_analysis, result, attempt_number)

        return ValidationReport(
            incident_id=analysis.incident_id,
            final_result=attempts[-1].result,
            attempts=attempts,
        )

    def apply(self, incident: Incident, analysis: AIAnalysis) -> AIAnalysis:
        report = self.retry_validate(incident, analysis)
        result = report.final_result
        analysis.validation_status = result.status
        analysis.validation_errors = result.errors or None
        return analysis
