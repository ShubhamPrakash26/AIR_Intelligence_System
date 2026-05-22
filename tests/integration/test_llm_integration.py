import os
import pytest

from src.incident.understanding_agent import IncidentUnderstandingAgent


@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Real LLM integration tests are skipped when OPENAI_API_KEY is not set",
)
def test_real_llm_integration_runs_and_returns_structured_output():
    """This test will run against the configured OpenAI key and model.

    It is intentionally guarded and will be skipped by default in CI.
    """
    agent = IncidentUnderstandingAgent()

    # Build a minimal incident payload for a realistic prompt
    from src.models.incident import Incident, PatientInfo, SurgeryInfo, IncidentDetails, AnesthesiaTechnique, OutcomeInfo, ContextMetadata
    from src.utils.helpers import generate_incident_id
    from datetime import datetime

    incident = Incident(
        incident_id=generate_incident_id(),
        patient=PatientInfo(age_range="21-30 years", sex="Female"),
        surgery=SurgeryInfo(type_of_procedure="Elective", surgical_branch="Gynecology", procedure="DHC"),
        incident=IncidentDetails(incident_description="Insufflator malfunction during laparoscopy", incident_details="Device failed on insufflation"),
        anesthesia=AnesthesiaTechnique(primary_technique="General Anesthesia", monitoring=["ECG", "Capnograph"]),
        medication_error=None,
        outcome=OutcomeInfo(outcome_category="E", patient_safety="Anesthetic delivered - surgery not done", harm_severity="High"),
        metadata=ContextMetadata(source_file="llm_test.xlsx", upload_date=datetime.now(), month="May", year=2026),
    )

    result = agent.analyze_incident(incident)
    analysis = result.analysis

    assert analysis.incident_id == incident.incident_id
    assert isinstance(analysis.confidence_score, float)
    assert analysis.severity in {"Low", "Moderate", "High", "Critical"}
