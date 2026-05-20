"""Test fixtures and sample data for testing."""

from datetime import datetime

import pandas as pd
import pytest

from src.models.analysis import AIAnalysis, Theme, VectorMetadata
from src.models.incident import (
    AnesthesiaTechnique,
    ContextMetadata,
    Incident,
    IncidentDetails,
    OutcomeInfo,
    PatientInfo,
    SurgeryInfo,
)
from src.utils.helpers import generate_incident_id


@pytest.fixture
def sample_incident() -> Incident:
    """Create a sample incident for testing."""
    incident_id = generate_incident_id()

    return Incident(
        incident_id=incident_id,
        patient=PatientInfo(
            age_range="21-30 years",
            sex="Female",
            weight_kg=65.0,
            height_cm=165,
            bmi=23.8,
            asa_grade="I",
        ),
        surgery=SurgeryInfo(
            type_of_procedure="Elective",
            surgical_branch="Gynecology",
            procedure="DHC",
        ),
        incident=IncidentDetails(
            incident_description="Equipment checked prior to surgery. After induction for GA with ETT and insertion of Veress needle, while attempting to insufflate, the insufflator malfunctioned.",
            incident_details="Insufflator malfunction during laparoscopy",
            time_of_incident="Working hours",
            place_of_incident="Operating room",
            timing_of_event="On induction",
            incident_detection="Clinically by surgeon",
        ),
        anesthesia=AnesthesiaTechnique(
            primary_technique="General Anesthesia",
            intubation_type="ETT",
            monitoring=["ECG", "Capnograph", "Pulse Oximeter", "NIBP"],
        ),
        medication_error=None,
        outcome=OutcomeInfo(
            outcome_category="E",
            patient_safety="Anesthetic delivered - surgery not done",
            harm_severity="Low",
        ),
        metadata=ContextMetadata(
            source_file="test_incidents.xlsx",
            upload_date=datetime.now(),
            month="May",
            year=2026,
        ),
    )


@pytest.fixture
def sample_ai_analysis(sample_incident: Incident) -> AIAnalysis:
    """Create a sample AI analysis for testing."""
    return AIAnalysis(
        incident_id=sample_incident.incident_id,
        incident_type=["Equipment Failure", "System Failure"],
        severity="High",
        severity_score=0.8,
        root_cause="Absence of functional pre-use verification of insufflator and inadequate biomedical escalation workflow",
        contributing_factors=[
            "Equipment maintenance gap",
            "Inadequate escalation procedure",
        ],
        key_learning="Multi-disciplinary coordination and equipment verification are essential",
        confidence_score=0.92,
        validation_status="valid",
        processing_timestamp=datetime.now().isoformat(),
        model_version="1.0.0",
    )


@pytest.fixture
def sample_excel_dataframe() -> pd.DataFrame:
    """Create a sample Excel-like DataFrame for testing."""
    data = {
        "Age Range": ["21-30 years", "31-40 years"],
        "Sex": ["Female", "Male"],
        "Weight": [65.0, 75.0],
        "Height": [165, 175],
        "BMI": [23.8, 24.5],
        "ASA Grade": ["I", "II"],
        "Type of Procedure": ["Elective", "Emergency"],
        "Surgical Branch": ["Gynecology", "Orthopedics"],
        "Procedure": ["DHC", "ORIF"],
        "Incident Narrative Description": [
            "Insufflator malfunction",
            "Wrong site surgery",
        ],
        "Describe Incident": [
            "Equipment failed during insufflation",
            "Site not verified",
        ],
        "Time of Incident": ["Working hours", "Working hours"],
        "Place of Incident": ["Operating room", "Operating room"],
        "Timing of Event": ["On induction", "Pre-incision"],
        "Incident Detection": ["Clinically by surgeon", "Clinically by surgeon"],
        "Primary": ["General Anesthesia", "General Anesthesia"],
        "ETT": ["ETT", "ETT"],
        "Patient Outcome Category": ["E", "D"],
        "Patient Safety": ["Anesthetic delivered - surgery not done", "Harm prevented"],
    }
    return pd.DataFrame(data)


@pytest.fixture
def sample_theme() -> Theme:
    """Create a sample theme for testing."""
    return Theme(
        theme_id="theme_001",
        theme_name="Medication Identification Safety Failures",
        theme_description="Incidents involving look-alike medications and identification failures",
        incident_count=14,
        incident_ids=[f"incident_{i}" for i in range(14)],
        patterns=[
            "Look-alike ampoules causing confusion",
            "Missing independent verification step",
        ],
        common_incident_types=["Medication Error", "Communication Failure"],
        common_root_causes=["Labeling failure", "Communication gap"],
        severity_distribution={"Low": 2, "Moderate": 5, "High": 7},
        average_severity_score=0.72,
        key_insight="Repeated failures in syringe labeling and verification procedures",
        recommendations=[
            "Implement color-coded syringe labels",
            "Require independent verification",
        ],
        created_timestamp=datetime.now().isoformat(),
        last_updated=datetime.now().isoformat(),
    )


@pytest.fixture
def sample_vector_metadata(sample_incident: Incident) -> VectorMetadata:
    """Create sample vector metadata for testing."""
    return VectorMetadata(
        incident_id=sample_incident.incident_id,
        incident_type=["Equipment Failure"],
        severity="High",
        severity_score=0.8,
        surgery_type="Gynecology",
        root_cause="Equipment maintenance gap",
        month="May",
        year=2026,
        source="test_incidents.xlsx",
        timestamp=datetime.now().isoformat(),
    )
