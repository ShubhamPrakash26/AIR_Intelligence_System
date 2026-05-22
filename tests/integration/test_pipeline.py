"""Integration tests for parse -> normalize pipeline."""

from src.ingestion.excel_parser import ExcelParser
from src.ingestion.validators import validate_incident_schema
from src.models.incident import Incident
from src.normalization.engine import NormalizationEngine
from src.incident.understanding_agent import IncidentUnderstandingAgent
from src.validation import ValidationAgent
from src.incident.root_cause_analyzer import RootCauseAnalyzer


def test_parse_to_normalize_pipeline_all_excel_files(excel_input_files):
    assert excel_input_files, "No Excel files found in data/inputs/excel or data/input/Excel"

    parser = ExcelParser()
    engine = NormalizationEngine()

    for sample in excel_input_files:
        incidents = parser.parse_file(sample)
        assert len(incidents) > 0, f"{sample}: parser returned no incidents"

        normalized = engine.normalize_incidents(incidents)

        assert len(normalized) == len(incidents), f"{sample}: normalize count mismatch"

        for item in normalized:
            # Validate the normalized payload can be re-validated by Pydantic model.
            payload = item.model_dump()
            rebuilt = Incident.model_validate(payload)
            assert rebuilt.incident_id == item.incident_id

            # Validate schema consistency and canonical fields.
            report = validate_incident_schema(rebuilt)
            assert report["is_valid"], f"{sample}: schema validation errors: {report['issues']}"
            assert rebuilt.patient.sex in {"Male", "Female", "Other", "Unknown", None}
            assert rebuilt.surgery.type_of_procedure in {"Elective", "Emergency", None}
            assert rebuilt.outcome.harm_severity in {"Low", "Moderate", "High", "Critical", None}


def test_full_week4_pipeline_from_excel_to_validation(excel_input_files):
    assert excel_input_files, "No Excel files found in data/inputs/excel or data/input/Excel"

    parser = ExcelParser()
    engine = NormalizationEngine()
    understanding_agent = IncidentUnderstandingAgent()
    validator = ValidationAgent()
    rca = RootCauseAnalyzer()

    sample = excel_input_files[0]
    incidents = parser.parse_file(sample)
    normalized = engine.normalize_incidents(incidents)

    target = normalized[0]
    analysis = understanding_agent.analyze_incident(target).analysis
    validation = validator.validate(target, analysis)
    root_cause = rca.analyze_incident(target, incident_types=analysis.incident_type, severity=analysis.severity)

    assert validation.status in {"valid", "needs_review", "invalid"}
    assert root_cause.root_cause
    assert root_cause.key_learning
    assert root_cause.contributing_factors
    assert analysis.root_cause == root_cause.root_cause
