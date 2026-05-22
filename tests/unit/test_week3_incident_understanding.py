from types import SimpleNamespace

from pydantic import ValidationError

from src.incident.classifiers import IncidentTypeClassifier
from src.incident.severity_analyzer import SeverityAnalyzer
from src.incident.understanding_agent import IncidentUnderstandingAgent
from src.models.analysis import AIAnalysis, IncidentUnderstandingResponse


def test_classifier_identifies_equipment_failure(sample_incident):
    classifier = IncidentTypeClassifier()

    result = classifier.classify_incident(sample_incident)

    assert "Equipment Failure" in result.labels
    assert result.confidence >= 0.55


def test_classifier_supports_multiple_labels(sample_incident):
    classifier = IncidentTypeClassifier()
    sample_incident.incident.incident_description = "Wrong site surgery due to communication failure and equipment malfunction"

    result = classifier.classify_incident(sample_incident)

    assert "Procedure-Related" in result.labels
    assert "Communication Failure" in result.labels
    assert "Equipment Failure" in result.labels
    assert result.labels.count("Procedure-Related") == 1


def test_classifier_falls_back_to_other_when_no_keywords(sample_incident):
    classifier = IncidentTypeClassifier()
    sample_incident.incident.incident_description = "An ambiguous event with no recognized taxonomy terms"
    sample_incident.incident.incident_details = "Routine observation"
    sample_incident.outcome.patient_safety = "No impact"
    sample_incident.outcome.morbidity = "None"
    sample_incident.outcome.personnel_safety = "None"
    sample_incident.outcome.patient_satisfaction = "None"

    result = classifier.classify_incident(sample_incident)

    assert result.labels == ["Other"]
    assert result.confidence == 0.35


def test_severity_analyzer_escalates_surgery_not_done(sample_incident):
    analyzer = SeverityAnalyzer()

    result = analyzer.analyze_incident(sample_incident)

    assert result.severity == "High"
    assert result.score >= 0.8
    assert "surgery" in result.rationale.lower()


def test_severity_analyzer_marks_critical_when_cardiac_arrest_is_present(sample_incident):
    analyzer = SeverityAnalyzer()
    sample_incident.outcome.patient_safety = "Post induction cardiac arrest with code blue response"

    result = analyzer.analyze_incident(sample_incident)

    assert result.severity == "Critical"
    assert result.score >= 0.95


def test_severity_analyzer_marks_moderate_for_near_miss(sample_incident):
    analyzer = SeverityAnalyzer()
    sample_incident.incident.incident_description = "Near miss due to delayed labeling reconciliation"
    sample_incident.incident.incident_details = "Routine observation"
    sample_incident.outcome.patient_safety = "No harm"
    sample_incident.outcome.morbidity = "None"
    sample_incident.outcome.personnel_safety = "None"
    sample_incident.outcome.patient_satisfaction = "None"

    result = analyzer.analyze_incident(sample_incident)

    assert result.severity == "Moderate"
    assert result.score == 0.6


def test_understanding_agent_produces_valid_ai_analysis(sample_incident):
    agent = IncidentUnderstandingAgent()

    result = agent.analyze_incident(sample_incident)

    assert result.analysis.incident_id == sample_incident.incident_id
    assert result.analysis.validation_status == "pending"
    assert "Equipment Failure" in result.analysis.incident_type
    assert result.analysis.severity == "High"

    validated = AIAnalysis.model_validate(result.analysis.model_dump())
    assert validated.incident_id == sample_incident.incident_id


def test_understanding_agent_uses_llm_payload_when_available(sample_incident):
    class FakeLLM:
        def invoke(self, messages):
            assert len(messages) == 2
            return SimpleNamespace(
                content=(
                    '{"incident_type": ["Medication Error", "Documentation Error"], "severity": "High", '
                    '"severity_score": 0.88, "root_cause": "Labeling failure", '
                    '"contributing_factors": ["Handwritten labels"], '
                    '"contributing_factor_categories": ["Medication Error", "Documentation Error"], '
                    '"key_learning": "Standardize labels", '
                    '"preventive_recommendations": ["Use barcode scanning"], '
                    '"confidence_score": 0.91, "processing_notes": "LLM override"}'
                )
            )

    agent = IncidentUnderstandingAgent(llm=FakeLLM())

    result = agent.analyze_incident(sample_incident)

    assert result.analysis.incident_type == ["Medication Error", "Documentation Error"]
    assert result.analysis.severity == "High"
    assert result.analysis.root_cause == "Labeling failure"
    assert result.analysis.processing_notes == "LLM override"


def test_llm_response_contract_is_strict_and_canonical():
    payload = {
        "incident_type": ["Equipment Failure", "Communication Failure"],
        "severity": "High",
        "severity_score": 0.91,
        "root_cause": "Equipment check and handoff gap",
        "contributing_factors": ["Missing equipment check", "Incomplete handoff"],
        "contributing_factor_categories": ["Equipment Failure", "Communication Failure"],
        "key_learning": "Use standardized checks",
        "preventive_recommendations": ["Add checklist"],
        "confidence_score": 0.89,
        "processing_notes": "Structured output",
    }

    result = IncidentUnderstandingResponse.model_validate(payload)

    assert result.severity.value == "High"
    assert result.model_dump(mode="json")["incident_type"] == ["Equipment Failure", "Communication Failure"]


def test_llm_response_contract_rejects_extra_fields():
    payload = {
        "incident_type": ["Equipment Failure"],
        "severity": "High",
        "severity_score": 0.9,
        "root_cause": "Equipment check gap",
        "contributing_factors": ["Missing check"],
        "key_learning": "Use checklist",
        "confidence_score": 0.8,
        "unexpected": "not allowed",
    }

    try:
        IncidentUnderstandingResponse.model_validate(payload)
    except ValidationError as exc:
        assert "extra_forbidden" in str(exc)
    else:
        raise AssertionError("Expected ValidationError for extra fields")
