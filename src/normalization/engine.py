"""Normalization engine for standardizing incident data."""

from __future__ import annotations

from src.models.incident import Incident
from src.normalization.mappers import (
    normalize_list_text,
    normalize_text,
    parse_date,
    map_incident_types,
    map_monitoring_list,
    map_outcome_category,
    map_surgical_branch,
    map_sex,
    map_procedure_type,
    map_severity,
)


class NormalizationEngine:
    """Normalize parsed incidents into canonical representations."""

    def normalize_incident(self, incident: Incident) -> Incident:
        """Normalize a single incident instance."""
        patient = incident.patient.model_copy(
            update={
                "age_range": normalize_text(incident.patient.age_range),
                "sex": map_sex(incident.patient.sex),
                "asa_grade": normalize_text(incident.patient.asa_grade),
            }
        )

        surgery = incident.surgery.model_copy(
            update={
                "type_of_procedure": map_procedure_type(incident.surgery.type_of_procedure),
                "surgical_branch": map_surgical_branch(incident.surgery.surgical_branch),
                "procedure": normalize_text(incident.surgery.procedure),
            }
        )

        incident_details = incident.incident.model_copy(
            update={
                "incident_description": normalize_text(incident.incident.incident_description),
                "incident_details": normalize_text(incident.incident.incident_details),
                "incident_type": map_incident_types(incident.incident.incident_type),
                "incident_relation": normalize_list_text(incident.incident.incident_relation),
                "time_of_incident": normalize_text(incident.incident.time_of_incident),
                "place_of_incident": normalize_text(incident.incident.place_of_incident),
                "timing_of_event": normalize_text(incident.incident.timing_of_event),
                "incident_detection": normalize_text(incident.incident.incident_detection),
            }
        )

        anesthesia = incident.anesthesia.model_copy(
            update={
                "primary_technique": normalize_text(incident.anesthesia.primary_technique),
                "supplementary_technique": normalize_list_text(incident.anesthesia.supplementary_technique),
                "monitoring": map_monitoring_list(incident.anesthesia.monitoring),
                "intubation_type": normalize_text(incident.anesthesia.intubation_type),
            }
        )

        outcome = incident.outcome.model_copy(
            update={
                "outcome_category": map_outcome_category(incident.outcome.outcome_category),
                "morbidity": normalize_text(incident.outcome.morbidity),
                "patient_safety": normalize_text(incident.outcome.patient_safety),
                "personnel_safety": normalize_text(incident.outcome.personnel_safety),
                "patient_satisfaction": normalize_text(incident.outcome.patient_satisfaction),
                "harm_severity": map_severity(incident.outcome.harm_severity),
            }
        )

        upload_date = incident.metadata.upload_date
        if upload_date is None and incident.raw_data:
            upload_date = parse_date(incident.raw_data.get("Date"))

        metadata = incident.metadata.model_copy(
            update={
                "source_file": normalize_text(incident.metadata.source_file),
                "institution": normalize_text(incident.metadata.institution),
                "region": normalize_text(incident.metadata.region),
                "upload_date": upload_date,
                "month": upload_date.strftime("%B") if upload_date else incident.metadata.month,
                "year": upload_date.year if upload_date else incident.metadata.year,
            }
        )

        return incident.model_copy(
            update={
                "patient": patient,
                "surgery": surgery,
                "incident": incident_details,
                "anesthesia": anesthesia,
                "outcome": outcome,
                "metadata": metadata,
            }
        )

    def normalize_incidents(self, incidents: list[Incident]) -> list[Incident]:
        """Normalize a batch of incidents."""
        return [self.normalize_incident(incident) for incident in incidents]
