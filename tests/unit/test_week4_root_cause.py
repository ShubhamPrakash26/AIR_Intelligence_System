from src.incident.root_cause_analyzer import RootCauseAnalyzer


def test_root_cause_analyzer_uses_grounded_fallback_for_ambiguous_incident(sample_incident):
    analyzer = RootCauseAnalyzer()
    ambiguous = sample_incident.model_copy(deep=True)
    ambiguous.incident.incident_description = "A routine event with no clear clinical details"
    ambiguous.incident.incident_details = ""
    ambiguous.surgery.type_of_procedure = None
    ambiguous.surgery.surgical_branch = None
    ambiguous.surgery.procedure = None
    ambiguous.anesthesia.primary_technique = None
    ambiguous.anesthesia.intubation_type = None
    ambiguous.anesthesia.monitoring = []
    ambiguous.outcome.patient_safety = "No impact"
    ambiguous.outcome.morbidity = "None"
    ambiguous.outcome.harm_severity = "Low"

    result = analyzer.analyze_incident(ambiguous, incident_types=[], severity="Low")

    assert result.systemic_failure_detected is False
    assert result.root_cause == "Insufficient detail for definitive root cause; manual review recommended"
    assert result.key_learning == "Document the event clearly and review local process gaps for prevention."
    assert result.contributing_factors[-1] == "Insufficient detail for definitive contributing factors; manual review recommended"


def test_root_cause_analyzer_identifies_equipment_failure(sample_incident):
    analyzer = RootCauseAnalyzer()

    result = analyzer.analyze_incident(sample_incident, incident_types=["Equipment Failure"], severity="High")

    assert result.systemic_failure_detected is True
    assert "Equipment" in result.root_cause
    assert "equipment" in " ".join(result.contributing_factors).lower()
    assert "verification" in result.key_learning.lower()