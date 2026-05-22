"""Unit tests for data models."""

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


class TestPatientInfo:
    """Tests for PatientInfo model."""

    def test_patient_info_creation(self):
        """Test creating a PatientInfo instance."""
        patient = PatientInfo(
            age_range="21-30 years",
            sex="Female",
            weight_kg=65.0,
            height_cm=165,
            asa_grade="I",
        )

        assert patient.age_range == "21-30 years"
        assert patient.sex == "Female"
        assert patient.weight_kg == 65.0
        assert patient.height_cm == 165

    def test_patient_info_optional_fields(self):
        """Test PatientInfo with optional fields."""
        patient = PatientInfo(
            age_range="21-30 years",
            sex="Female",
        )

        assert patient.weight_kg is None
        assert patient.bmi is None

    def test_patient_info_validation(self):
        """Test PatientInfo Pydantic validation."""
        # Should accept None values
        patient = PatientInfo()
        assert patient.age_range is None
        assert patient.sex is None


class TestSurgeryInfo:
    """Tests for SurgeryInfo model."""

    def test_surgery_info_creation(self):
        """Test creating a SurgeryInfo instance."""
        surgery = SurgeryInfo(
            type_of_procedure="Elective",
            surgical_branch="Gynecology",
            procedure="DHC",
        )

        assert surgery.type_of_procedure == "Elective"
        assert surgery.surgical_branch == "Gynecology"
        assert surgery.procedure == "DHC"

    def test_surgery_info_optional(self):
        """Test SurgeryInfo with optional fields."""
        surgery = SurgeryInfo()
        assert surgery.type_of_procedure is None


class TestIncidentDetails:
    """Tests for IncidentDetails model."""

    def test_incident_details_creation(self):
        """Test creating IncidentDetails."""
        incident = IncidentDetails(
            incident_description="Insufflator malfunction",
            incident_details="Equipment failed",
            time_of_incident="Working hours",
            place_of_incident="Operating room",
        )

        assert incident.incident_description == "Insufflator malfunction"
        assert incident.place_of_incident == "Operating room"

    def test_incident_details_with_lists(self):
        """Test IncidentDetails with list fields."""
        incident = IncidentDetails(
            incident_type=["Equipment Failure", "System Failure"],
            incident_relation=["To Surgery"],
        )

        assert len(incident.incident_type) == 2
        assert "Equipment Failure" in incident.incident_type


class TestAnesthesiaTechnique:
    """Tests for AnesthesiaTechnique model."""

    def test_anesthesia_technique_creation(self):
        """Test creating AnesthesiaTechnique."""
        anesthesia = AnesthesiaTechnique(
            primary_technique="General Anesthesia",
            intubation_type="ETT",
            monitoring=["ECG", "Capnograph"],
        )

        assert anesthesia.primary_technique == "General Anesthesia"
        assert len(anesthesia.monitoring) == 2


class TestOutcomeInfo:
    """Tests for OutcomeInfo model."""

    def test_outcome_info_creation(self):
        """Test creating OutcomeInfo."""
        outcome = OutcomeInfo(
            outcome_category="E",
            harm_severity="Low",
            patient_safety="Anesthetic delivered - surgery not done",
        )

        assert outcome.outcome_category == "E"
        assert outcome.harm_severity == "Low"

    def test_outcome_with_severity_levels(self):
        """Test OutcomeInfo with different severity levels."""

        def test_ai_analysis_validation_status_rejects_unknown(self):
            """Test AIAnalysis validation rules for validation_status."""
            with pytest.raises(ValueError, match="validation_status"):
                AIAnalysis(
                    incident_id="test",
                    incident_type=["Equipment Failure"],
                    severity="High",
                    severity_score=0.8,
                    root_cause="Test",
                    contributing_factors=["Test"],
                    key_learning="Test",
                    confidence_score=0.9,
                    validation_status="unexpected",
                    processing_timestamp="2026-05-20T10:00:00Z",
                    model_version="1.0.0",
                )
        for severity in ["Low", "Moderate", "High", "Critical"]:
            outcome = OutcomeInfo(harm_severity=severity)
            assert outcome.harm_severity == severity


class TestContextMetadata:
    """Tests for ContextMetadata model."""

    def test_metadata_creation(self):
        """Test creating ContextMetadata."""
        metadata = ContextMetadata(
            source_file="incidents.xlsx",
            institution="Sample Hospital",
            month="May",
            year=2026,
        )

        assert metadata.source_file == "incidents.xlsx"
        assert metadata.year == 2026


class TestIncident:
    """Tests for Incident model."""

    def test_incident_creation(self, sample_incident: Incident):
        """Test creating a complete Incident."""
        assert sample_incident.incident_id is not None
        assert sample_incident.patient.age_range == "21-30 years"
        assert sample_incident.surgery.surgical_branch == "Gynecology"
        assert sample_incident.outcome.outcome_category == "E"

    def test_incident_validation(self, sample_incident: Incident):
        """Test Incident Pydantic validation."""
        # Should have all required fields
        assert sample_incident.incident_id
        assert sample_incident.patient
        assert sample_incident.surgery
        assert sample_incident.incident
        assert sample_incident.anesthesia
        assert sample_incident.outcome
        assert sample_incident.metadata

    def test_incident_optional_medication_error(self, sample_incident: Incident):
        """Test Incident with optional medication error."""
        assert sample_incident.medication_error is None


class TestAIAnalysis:
    """Tests for AIAnalysis model."""

    def test_ai_analysis_creation(self, sample_ai_analysis: AIAnalysis):
        """Test creating AIAnalysis."""
        assert sample_ai_analysis.incident_id is not None
        assert sample_ai_analysis.severity in ["Low", "Moderate", "High", "Critical"]
        assert 0 <= sample_ai_analysis.severity_score <= 1
        assert 0 <= sample_ai_analysis.confidence_score <= 1

    def test_ai_analysis_validation_status(self):
        """Test AIAnalysis validation status."""
        analysis = AIAnalysis(
            incident_id="test",
            incident_type=["Equipment Failure"],
            severity="High",
            severity_score=0.8,
            root_cause="Test",
            contributing_factors=["Test"],
            key_learning="Test",
            confidence_score=0.9,
            processing_timestamp="2026-05-20T10:00:00Z",
            model_version="1.0.0",
        )

        assert analysis.validation_status == "pending"

    def test_ai_analysis_multi_label(self):
        """Test AIAnalysis with multiple incident types."""
        analysis = AIAnalysis(
            incident_id="test",
            incident_type=["Equipment Failure", "Communication Failure", "Human Error"],
            severity="Critical",
            severity_score=0.95,
            root_cause="Multiple systemic failures",
            contributing_factors=["Factor 1", "Factor 2"],
            key_learning="Learning",
            confidence_score=0.85,
            processing_timestamp="2026-05-20T10:00:00Z",
            model_version="1.0.0",
        )

        assert len(analysis.incident_type) == 3


class TestTheme:
    """Tests for Theme model."""

    def test_theme_creation(self, sample_theme: Theme):
        """Test creating a Theme."""
        assert sample_theme.theme_id is not None
        assert sample_theme.incident_count == 14
        assert len(sample_theme.incident_ids) == 14
        assert len(sample_theme.patterns) >= 1

    def test_theme_severity_distribution(self, sample_theme: Theme):
        """Test theme severity distribution."""
        total = sum(sample_theme.severity_distribution.values())
        assert total == sample_theme.incident_count


class TestVectorMetadata:
    """Tests for VectorMetadata model."""

    def test_vector_metadata_creation(self, sample_vector_metadata: VectorMetadata):
        """Test creating VectorMetadata."""
        assert sample_vector_metadata.incident_id is not None
        assert len(sample_vector_metadata.incident_type) >= 1
        assert 0 <= sample_vector_metadata.severity_score <= 1

    def test_vector_metadata_optional_fields(self):
        """Test VectorMetadata with optional fields."""
        metadata = VectorMetadata(
            incident_id="test",
            incident_type=["Test"],
            severity="High",
            severity_score=0.8,
            surgery_type="Gynecology",
            root_cause="Test",
            source="test.xlsx",
            timestamp="2026-05-20T10:00:00Z",
        )

        assert metadata.month is None
        assert metadata.year is None
