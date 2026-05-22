from src.validation import ValidationAgent


def test_validation_agent_marks_high_risk_low_severity_as_invalid(sample_incident):
    agent = ValidationAgent()
    from src.incident.understanding_agent import IncidentUnderstandingAgent

    result = IncidentUnderstandingAgent().analyze_incident(sample_incident).analysis
    result.severity = "Low"

    validation = agent.validate(sample_incident, result)

    assert validation.status == "invalid"
    assert any("severity=Low" in error for error in validation.errors)


def test_validation_agent_retry_validate_returns_report(sample_incident):
    agent = ValidationAgent()
    from src.incident.understanding_agent import IncidentUnderstandingAgent

    result = IncidentUnderstandingAgent().analyze_incident(sample_incident).analysis
    result.severity = "Low"

    def repair_fn(_incident, current_analysis, _validation_result, _attempt_number):
        repaired = current_analysis.model_copy(deep=True)
        repaired.severity = "High"
        return repaired

    report = agent.retry_validate(sample_incident, result, repair_fn=repair_fn, max_attempts=2)

    assert report.incident_id == sample_incident.incident_id
    assert len(report.attempts) == 2
    assert report.attempts[0].result.status == "invalid"
    assert report.final_result.status == "valid"

