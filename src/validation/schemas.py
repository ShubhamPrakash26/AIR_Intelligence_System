from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


ValidationStatus = Literal["pending", "valid", "needs_review", "invalid"]


class ValidationResult(BaseModel):
    status: ValidationStatus = Field(..., description="Validation outcome for an analysis")
    errors: list[str] = Field(default_factory=list, description="Blocking validation errors")
    warnings: list[str] = Field(default_factory=list, description="Non-blocking validation warnings")
    validated_at: datetime = Field(default_factory=datetime.utcnow)
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _normalize_lists(self) -> "ValidationResult":
        self.errors = list(dict.fromkeys(self.errors))
        self.warnings = list(dict.fromkeys(self.warnings))
        return self


class ValidationOutputConstraints(BaseModel):
    """Static contract describing what a valid validation outcome must satisfy."""

    allowed_statuses: tuple[ValidationStatus, ...] = Field(
        default=("pending", "valid", "needs_review", "invalid"),
        description="Permitted validation statuses",
    )
    required_nonempty_fields: tuple[str, ...] = Field(
        default=("incident_type", "root_cause", "contributing_factors", "key_learning"),
        description="AIAnalysis fields that must not be empty",
    )
    max_error_count: int = Field(default=10, ge=1, description="Maximum number of validation errors to retain")
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _normalize(self) -> "ValidationOutputConstraints":
        self.allowed_statuses = tuple(dict.fromkeys(self.allowed_statuses))
        self.required_nonempty_fields = tuple(dict.fromkeys(self.required_nonempty_fields))
        return self


class ValidationAttempt(BaseModel):
    attempt_number: int = Field(..., ge=1, description="1-based validation attempt number")
    result: ValidationResult = Field(..., description="Result captured for this attempt")
    model_config = ConfigDict(extra="forbid")


class ValidationReport(BaseModel):
    incident_id: str = Field(..., description="Incident identifier for the report")
    final_result: ValidationResult = Field(..., description="Final validation result")
    attempts: list[ValidationAttempt] = Field(default_factory=list, description="All validation attempts")
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _normalize_attempts(self) -> "ValidationReport":
        self.attempts = sorted(self.attempts, key=lambda attempt: attempt.attempt_number)
        return self
