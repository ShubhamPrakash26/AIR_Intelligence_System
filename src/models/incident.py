"""Data models for incident information."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class PatientInfo(BaseModel):
    """Patient demographic and clinical information."""

    age_range: Optional[str] = Field(None, description="Age range (e.g., '21-30 years')")
    sex: Optional[str] = Field(None, description="Patient sex (M/F)")
    weight_kg: Optional[float] = Field(None, description="Weight in kilograms")
    height_cm: Optional[float] = Field(None, description="Height in centimeters")
    bmi: Optional[float] = Field(None, description="Body Mass Index")
    asa_grade: Optional[str] = Field(None, description="ASA physical status grade (I-VI)")


class SurgeryInfo(BaseModel):
    """Surgical procedure information."""

    type_of_procedure: Optional[str] = Field(None, description="Type of procedure (Elective/Emergency)")
    surgical_branch: Optional[str] = Field(None, description="Surgical specialty (e.g., Gynecology)")
    procedure: Optional[str] = Field(None, description="Specific procedure name")
    duration_minutes: Optional[int] = Field(None, description="Procedure duration in minutes")


class AnesthesiaTechnique(BaseModel):
    """Anesthesia technique and monitoring."""

    primary_technique: Optional[str] = Field(None, description="Primary anesthesia technique")
    supplementary_technique: Optional[List[str]] = Field(
        None, description="Supplementary techniques"
    )
    monitoring: Optional[List[str]] = Field(
        None, description="Monitoring modalities used"
    )
    intubation_type: Optional[str] = Field(None, description="ETT or other airway type")


class IncidentDetails(BaseModel):
    """Core incident information."""

    incident_description: Optional[str] = Field(None, description="Incident narrative description")
    incident_details: Optional[str] = Field(None, description="Detailed incident description")
    incident_type: Optional[List[str]] = Field(
        None, description="Types of incident (multi-label)"
    )
    time_of_incident: Optional[str] = Field(None, description="Time of incident (e.g., 'Working hours')")
    place_of_incident: Optional[str] = Field(None, description="Location (e.g., 'Operating room')")
    timing_of_event: Optional[str] = Field(None, description="Phase of event (e.g., 'On induction')")
    incident_detection: Optional[str] = Field(None, description="How incident was detected")
    incident_relation: Optional[List[str]] = Field(None, description="Relation to surgery/anesthesia")


class MedicationError(BaseModel):
    """Medication error details."""

    type_of_error: Optional[str] = Field(None, description="Type of medication error")
    cause_of_error: Optional[str] = Field(None, description="Root cause of error")
    drug_name: Optional[str] = Field(None, description="Name of drug involved")
    dose: Optional[str] = Field(None, description="Dose involved")


class OutcomeInfo(BaseModel):
    """Patient outcome information."""

    outcome_category: Optional[str] = Field(
        None, description="AIR outcome category (A-E)"
    )
    morbidity: Optional[str] = Field(None, description="Morbidity outcome")
    patient_safety: Optional[str] = Field(None, description="Patient safety impact")
    personnel_safety: Optional[str] = Field(None, description="Personnel safety impact")
    patient_satisfaction: Optional[str] = Field(None, description="Patient satisfaction impact")
    harm_severity: Optional[str] = Field(None, description="Severity of harm (Low/Moderate/High/Critical)")


class ContextMetadata(BaseModel):
    """Contextual metadata about the incident."""

    source_file: Optional[str] = Field(None, description="Source file name")
    upload_date: Optional[datetime] = Field(None, description="Date of data upload")
    institution: Optional[str] = Field(None, description="Institution/Hospital name")
    region: Optional[str] = Field(None, description="Geographic region")
    month: Optional[str] = Field(None, description="Month of incident")
    year: Optional[int] = Field(None, description="Year of incident")


class Incident(BaseModel):
    """Complete incident record."""

    incident_id: str = Field(..., description="Unique incident identifier (UUID)")
    patient: PatientInfo = Field(..., description="Patient information")
    surgery: SurgeryInfo = Field(..., description="Surgical information")
    incident: IncidentDetails = Field(..., description="Incident details")
    anesthesia: AnesthesiaTechnique = Field(..., description="Anesthesia technique")
    medication_error: Optional[MedicationError] = Field(None, description="Medication error details if applicable")
    outcome: OutcomeInfo = Field(..., description="Outcome information")
    metadata: ContextMetadata = Field(..., description="Contextual metadata")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Raw input data for reference")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "incident_id": "550e8400-e29b-41d4-a716-446655440000",
                "patient": {
                    "age_range": "21-30 years",
                    "sex": "Female",
                    "weight_kg": 65,
                    "height_cm": 165,
                    "asa_grade": "I",
                },
                "surgery": {
                    "type_of_procedure": "Elective",
                    "surgical_branch": "Gynecology",
                    "procedure": "DHC",
                },
                "incident": {
                    "incident_description": "Insufflator malfunction during laparoscopy",
                    "time_of_incident": "Working hours",
                    "place_of_incident": "Operating room",
                    "timing_of_event": "On induction",
                },
                "anesthesia": {
                    "primary_technique": "General Anesthesia",
                    "intubation_type": "ETT",
                    "monitoring": ["ECG", "Capnograph", "Pulse Oximeter"],
                },
                "outcome": {
                    "outcome_category": "E",
                    "patient_safety": "Anesthetic delivered - surgery not done",
                    "harm_severity": "Low",
                },
                "metadata": {
                    "source_file": "incidents_batch_001.xlsx",
                    "upload_date": "2026-05-20T10:00:00",
                    "institution": "Sample Hospital",
                },
            }
        }
    )
