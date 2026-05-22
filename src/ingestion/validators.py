"""Schema validation utilities for parsed incidents."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from src.models.analysis import AIAnalysis, Theme, VectorMetadata
from src.models.incident import Incident
from src.normalization.enums import (
    MonitoringType,
    OutcomeCategory,
    ProcedureType,
    SeverityLevel,
    SexType,
)


def _issue(
    code: str,
    severity: str,
    field: str,
    message: str,
    value: Any = None,
    expected: list[str] | None = None,
) -> dict[str, Any]:
    """Create a normalized validation issue structure."""
    return {
        "code": code,
        "severity": severity,
        "field": field,
        "message": message,
        "value": value,
        "expected": expected,
    }


def _validate_enum_value(
    issues: list[dict[str, Any]],
    field: str,
    value: str | None,
    valid_values: set[str],
    required: bool = False,
) -> None:
    if value is None:
        if required:
            issues.append(
                _issue(
                    code="missing_required_field",
                    severity="error",
                    field=field,
                    message="Required field is missing",
                    expected=sorted(valid_values),
                )
            )
        return

    if value not in valid_values:
        issues.append(
            _issue(
                code="invalid_enum_value",
                severity="error",
                field=field,
                message="Value is not part of canonical taxonomy",
                value=value,
                expected=sorted(valid_values),
            )
        )


def generate_json_schema_artifacts(output_dir: str | Path) -> dict[str, str]:
    """Generate JSON schema artifacts for core models.

    Returns a mapping from model name to generated schema file path.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    schema_map = {
        "Incident": Incident,
        "AIAnalysis": AIAnalysis,
        "Theme": Theme,
        "VectorMetadata": VectorMetadata,
    }

    written: dict[str, str] = {}
    for name, model in schema_map.items():
        schema_path = out / f"{name.lower()}.schema.json"
        schema_path.write_text(json.dumps(model.model_json_schema(), indent=2), encoding="utf-8")
        written[name] = str(schema_path)

    return written


def validate_incident_schema(incident: Incident | dict[str, Any]) -> dict[str, Any]:
    """Validate an Incident object with structural and semantic checks.

    Returns:
        {
          "is_valid": bool,
          "error_count": int,
          "warning_count": int,
          "issues": list[dict],
        }
    """
    issues: list[dict[str, Any]] = []

    model: Incident
    if isinstance(incident, Incident):
        model = incident
    else:
        try:
            model = Incident.model_validate(incident)
        except ValidationError as exc:
            for e in exc.errors():
                field = ".".join(str(p) for p in e.get("loc", []))
                issues.append(
                    _issue(
                        code="pydantic_validation_error",
                        severity="error",
                        field=field,
                        message=e.get("msg", "Validation error"),
                        value=e.get("input"),
                    )
                )
            return {
                "is_valid": False,
                "error_count": len(issues),
                "warning_count": 0,
                "issues": issues,
            }

    if not model.incident_id:
        issues.append(
            _issue(
                code="missing_required_field",
                severity="error",
                field="incident_id",
                message="Incident ID is required",
            )
        )

    _validate_enum_value(
        issues,
        field="patient.sex",
        value=model.patient.sex,
        valid_values={v.value for v in SexType},
        required=False,
    )

    _validate_enum_value(
        issues,
        field="surgery.type_of_procedure",
        value=model.surgery.type_of_procedure,
        valid_values={v.value for v in ProcedureType},
        required=False,
    )

    _validate_enum_value(
        issues,
        field="outcome.harm_severity",
        value=model.outcome.harm_severity,
        valid_values={v.value for v in SeverityLevel},
        required=False,
    )

    _validate_enum_value(
        issues,
        field="outcome.outcome_category",
        value=model.outcome.outcome_category,
        valid_values={v.value for v in OutcomeCategory},
        required=False,
    )

    if model.anesthesia.monitoring:
        valid_monitoring = {m.value for m in MonitoringType}
        for idx, mon in enumerate(model.anesthesia.monitoring):
            if mon not in valid_monitoring:
                issues.append(
                    _issue(
                        code="unknown_monitoring_label",
                        severity="warning",
                        field=f"anesthesia.monitoring[{idx}]",
                        message="Monitoring label is not canonical",
                        value=mon,
                        expected=sorted(valid_monitoring),
                    )
                )

    if not model.incident.incident_description and not model.incident.incident_details:
        issues.append(
            _issue(
                code="weak_context",
                severity="warning",
                field="incident",
                message="Both incident description and incident details are empty",
            )
        )

    error_count = len([i for i in issues if i["severity"] == "error"])
    warning_count = len([i for i in issues if i["severity"] == "warning"])

    return {
        "is_valid": error_count == 0,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": issues,
    }

def validate_incidents_batch(incidents: list[Incident]) -> dict[str, Any]:
    """Validate a batch of incidents and return aggregate diagnostics."""
    invalid = 0
    total_errors = 0
    total_warnings = 0
    details: list[dict[str, Any]] = []

    for inc in incidents:
        res = validate_incident_schema(inc)
        total_errors += res["error_count"]
        total_warnings += res["warning_count"]
        if not res["is_valid"]:
            invalid += 1
        details.append({"incident_id": inc.incident_id, **res})

    return {
        "total": len(incidents),
        "invalid": invalid,
        "valid": len(incidents) - invalid,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
        "details": details,
    }
