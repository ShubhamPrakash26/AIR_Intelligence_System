"""Data models for AI analysis outputs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.normalization.enums import IncidentType, SeverityLevel


class IncidentUnderstandingResponse(BaseModel):
    """Strict JSON contract expected from the LLM layer.

    The agent converts this structured response into the richer AIAnalysis
    output model after validation.
    """

    incident_type: list[IncidentType] = Field(..., min_length=1, description="Canonical incident types")
    severity: SeverityLevel = Field(..., description="Canonical severity level")
    severity_score: float = Field(..., ge=0, le=1, description="Numerical severity score (0-1)")
    root_cause: str = Field(..., min_length=1, description="Systemic root cause")
    contributing_factors: list[str] = Field(..., min_length=1, description="Contributing factors")
    contributing_factor_categories: list[IncidentType] | None = Field(
        None, description="Canonical contributing factor categories"
    )
    key_learning: str = Field(..., min_length=1, description="Key preventive learning")
    preventive_recommendations: list[str] | None = Field(
        None, description="Specific preventive recommendations"
    )
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in the analysis (0-1)")
    processing_notes: str | None = Field(None, description="Additional notes from the model")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_semantics(self) -> "IncidentUnderstandingResponse":
        if not self.incident_type:
            raise ValueError("incident_type must not be empty")
        if not self.contributing_factors:
            raise ValueError("contributing_factors must not be empty")
        return self


class IncidentAnalysisBatchResponse(BaseModel):
    """Explicit response model for incident analysis endpoints."""

    count: int = Field(..., ge=0, description="Number of incidents analyzed")
    analyses: list["AIAnalysis"] = Field(..., description="Per-incident analysis results")

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_batch(self) -> "IncidentAnalysisBatchResponse":
        if self.count != len(self.analyses):
            raise ValueError("count must match the number of analyses")
        return self


class AIAnalysis(BaseModel):
    """AI-generated analysis of an incident."""

    incident_id: str = Field(..., description="Reference to the incident ID")

    # Classification
    incident_type: list[str] = Field(..., description="Multi-label incident classification")

    # Severity Analysis
    severity: str = Field(..., description="Severity level (Low/Moderate/High/Critical)")
    severity_score: float = Field(..., ge=0, le=1, description="Numerical severity score (0-1)")

    # Root Cause Analysis
    root_cause: str = Field(..., description="Systemic root cause (not just event description)")
    contributing_factors: list[str] = Field(..., description="Contributing factors to the incident")
    contributing_factor_categories: list[str] | None = Field(
        None, description="Categories of contributing factors"
    )

    # Learning & Prevention
    key_learning: str = Field(..., description="Key preventive learning from the incident")
    preventive_recommendations: list[str] | None = Field(
        None, description="Specific preventive recommendations"
    )

    # Quality Metrics
    confidence_score: float = Field(..., ge=0, le=1, description="Confidence in the analysis (0-1)")
    validation_status: str = Field(
        default="pending", description="Validation status (valid/invalid/needs_review)"
    )
    validation_errors: list[str] | None = Field(
        None, description="List of validation errors if any"
    )

    # Processing Metadata
    processing_timestamp: str = Field(..., description="ISO timestamp of analysis")
    model_version: str = Field(..., description="Version of AI model used")
    processing_notes: str | None = Field(None, description="Additional notes")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "550e8400-e29b-41d4-a716-446655440000",
                "incident_type": ["Equipment Failure", "System Failure"],
                "severity": "High",
                "severity_score": 0.8,
                "root_cause": "Absence of functional pre-use verification of insufflator and inadequate biomedical escalation workflow",
                "contributing_factors": [
                    "Equipment maintenance gap",
                    "Inadequate escalation procedure",
                    "Limited communication between teams",
                ],
                "key_learning": "Multi-disciplinary coordination and standardized equipment verification protocols are essential for perioperative safety",
                "confidence_score": 0.92,
                "validation_status": "valid",
                "processing_timestamp": "2026-05-20T10:30:00Z",
                "model_version": "1.0.0",
            }
        }
    )

    @model_validator(mode="after")
    def _validate_model(self) -> "AIAnalysis":
        allowed_statuses = {"pending", "valid", "invalid", "needs_review"}
        if self.validation_status not in allowed_statuses:
            raise ValueError(f"validation_status must be one of {sorted(allowed_statuses)}")
        return self


class Theme(BaseModel):
    """Clustering theme from incident analysis."""

    theme_id: str = Field(..., description="Unique theme identifier")
    theme_name: str = Field(..., description="Name of the theme")
    theme_description: str = Field(..., description="Description of the theme")

    # Composition
    incident_count: int = Field(..., description="Number of incidents in this theme")
    incident_ids: list[str] = Field(..., description="List of incident IDs in theme")

    # Patterns
    patterns: list[str] = Field(..., description="Key patterns identified in theme")
    common_incident_types: list[str] = Field(..., description="Common incident types in theme")
    common_root_causes: list[str] = Field(..., description="Common root causes in theme")

    # Statistics
    severity_distribution: dict = Field(..., description="Distribution of severity levels")
    average_severity_score: float = Field(..., description="Mean severity score")

    # Insights
    key_insight: str = Field(..., description="Key insight from this theme")
    recommendations: list[str] = Field(..., description="Theme-specific recommendations")

    # Metadata
    created_timestamp: str = Field(..., description="ISO timestamp of theme creation")
    last_updated: str = Field(..., description="ISO timestamp of last update")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "theme_id": "theme_001",
                "theme_name": "Medication Identification Safety Failures",
                "theme_description": "Incidents involving look-alike medications and identification failures",
                "incident_count": 14,
                "patterns": [
                    "Look-alike ampoules causing confusion",
                    "Missing independent verification step",
                    "Communication breakdown in medication handover",
                ],
                "common_incident_types": ["Medication Error", "Communication Failure"],
                "key_insight": "Repeated failures in syringe labeling and verification procedures",
                "recommendations": [
                    "Implement color-coded syringe labels",
                    "Require independent verification by two clinicians",
                    "Enhance pharmacy dispensing procedures",
                ],
                "created_timestamp": "2026-05-20T11:00:00Z",
            }
        }
    )


class VectorMetadata(BaseModel):
    """Metadata stored with incident vectors in Qdrant."""

    incident_id: str = Field(..., description="Incident identifier")
    incident_type: list[str] = Field(..., description="Incident types (multi-label)")
    severity: str = Field(..., description="Severity level")
    severity_score: float = Field(..., description="Numerical severity score")
    surgery_type: str = Field(..., description="Type of surgery")
    root_cause: str = Field(..., description="Root cause description")
    key_learning: str = Field(default="", description="Key preventive learning from analysis")
    month: str | None = Field(None, description="Month of incident")
    year: int | None = Field(None, description="Year of incident")
    source: str = Field(..., description="Data source")
    timestamp: str = Field(..., description="ISO timestamp")
    source_type: str = Field(
        default="incident_report",
        description="Origin type: 'incident_report', 'literature', 'guideline', 'protocol'",
    )
    title: str | None = Field(
        None,
        description="Document title (used for literature/guidelines; None for incident reports)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "550e8400-e29b-41d4-a716-446655440000",
                "incident_type": ["Equipment Failure"],
                "severity": "High",
                "severity_score": 0.8,
                "surgery_type": "Gynecology",
                "root_cause": "Equipment maintenance gap",
                "month": "May",
                "year": 2026,
                "source": "incidents_batch_001.xlsx",
                "timestamp": "2026-05-20T10:00:00Z",
            }
        }
    )
