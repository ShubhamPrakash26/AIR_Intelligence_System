"""Unit tests for normalization modules."""

from datetime import datetime
from pathlib import Path

from src.ingestion.validators import (
    generate_json_schema_artifacts,
    validate_incident_schema,
)
from src.normalization.engine import NormalizationEngine
from src.normalization.mappers import missing_to_none, normalize_bool, normalize_choice, parse_date


def test_missing_to_none_tokens():
    assert missing_to_none("") is None
    assert missing_to_none("NA") is None
    assert missing_to_none("null") is None
    assert missing_to_none("value") == "value"


def test_normalize_bool_values():
    assert normalize_bool("Yes") is True
    assert normalize_bool("n") is False
    assert normalize_bool("maybe") is None


def test_normalize_choice_case_insensitive():
    mapping = {"male": "Male", "female": "Female"}
    assert normalize_choice("MALE", mapping) == "Male"
    assert normalize_choice(" female ", mapping) == "Female"


def test_parse_date_formats():
    dt = parse_date("13-04-2026")
    assert isinstance(dt, datetime)
    assert dt.year == 2026


def test_normalize_incident(sample_incident):
    engine = NormalizationEngine()

    # inject messy values
    dirty = sample_incident.model_copy(
        update={
            "patient": sample_incident.patient.model_copy(update={"sex": "female ", "age_range": " 21-30 years "}),
            "surgery": sample_incident.surgery.model_copy(update={"type_of_procedure": " emergency "}),
            "outcome": sample_incident.outcome.model_copy(update={"harm_severity": " high "}),
            "raw_data": {"Date": "13-04-2026"},
            "metadata": sample_incident.metadata.model_copy(update={"upload_date": None, "month": None, "year": None}),
        }
    )

    normalized = engine.normalize_incident(dirty)

    assert normalized.patient.sex == "Female"
    assert normalized.patient.age_range == "21-30 years"
    assert normalized.surgery.type_of_procedure == "Emergency"
    assert normalized.outcome.harm_severity == "High"
    assert normalized.metadata.year == 2026
    assert normalized.metadata.month == "April"


def test_validate_incident_schema(sample_incident):
    res = validate_incident_schema(sample_incident)
    assert res["is_valid"] is True


def test_procedure_mapping(sample_incident):
    engine = NormalizationEngine()
    dirty = sample_incident.model_copy(
        update={"surgery": sample_incident.surgery.model_copy(update={"type_of_procedure": " emergent "})}
    )
    normalized = engine.normalize_incident(dirty)
    assert normalized.surgery.type_of_procedure == "Emergency"


def test_branch_and_monitoring_canonicalization(sample_incident):
    engine = NormalizationEngine()
    dirty = sample_incident.model_copy(
        update={
            "surgery": sample_incident.surgery.model_copy(update={"surgical_branch": " orthopaedics "}),
            "anesthesia": sample_incident.anesthesia.model_copy(
                update={"monitoring": ["spo2", "ETCO2", "nibp", "ecg"]}
            ),
            "incident": sample_incident.incident.model_copy(
                update={"incident_type": ["medication", "equipment failure", "communication"]}
            ),
            "outcome": sample_incident.outcome.model_copy(update={"outcome_category": " e "}),
        }
    )

    normalized = engine.normalize_incident(dirty)
    assert normalized.surgery.surgical_branch == "Orthopedics"
    assert normalized.anesthesia.monitoring == ["Pulse Oximeter", "Capnograph", "NIBP", "ECG"]
    assert normalized.incident.incident_type == [
        "Medication Error",
        "Equipment Failure",
        "Communication Failure",
    ]
    assert normalized.outcome.outcome_category == "E"


def test_validator_rich_error_reporting(sample_incident):
    bad_payload = sample_incident.model_dump()
    bad_payload["patient"]["sex"] = "Alien"
    bad_payload["outcome"]["harm_severity"] = "Severe"

    report = validate_incident_schema(bad_payload)
    assert report["is_valid"] is False
    assert report["error_count"] >= 2
    assert any(i["field"] == "patient.sex" for i in report["issues"])
    assert any(i["field"] == "outcome.harm_severity" for i in report["issues"])


def test_generate_json_schema_artifacts(temp_data_dir):
    output_dir = Path(temp_data_dir) / "schemas"
    result = generate_json_schema_artifacts(output_dir)

    assert "Incident" in result
    assert "AIAnalysis" in result
    assert "Theme" in result
    assert "VectorMetadata" in result

    for _, file_path in result.items():
        assert Path(file_path).exists()
