"""Value mappers used by the normalization engine."""

from __future__ import annotations

import re
from datetime import datetime

from src.normalization.enums import (
    BOOLEAN_FALSE_TOKENS,
    BOOLEAN_TRUE_TOKENS,
    MISSING_TOKENS,
)
from src.utils.helpers import normalize_whitespace


DATE_FORMATS = (
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%d-%m-%y",
    "%d/%m/%y",
)


# Canonical mapping tables for normalization
SEX_MAPPING = {
    "m": "Male",
    "male": "Male",
    "f": "Female",
    "female": "Female",
    "other": "Other",
    "unknown": "Unknown",
}

PROCEDURE_MAPPING = {
    "elective": "Elective",
    "emergency": "Emergency",
    "emergent": "Emergency",
}

SEVERITY_MAPPING = {
    "low": "Low",
    "moderate": "Moderate",
    "high": "High",
    "critical": "Critical",
}

OUTCOME_CATEGORY_MAPPING = {
    "a": "A",
    "b": "B",
    "c": "C",
    "d": "D",
    "e": "E",
    "d1": "D",
    "d2": "D",
    "d3": "D",
}

SURGICAL_BRANCH_MAPPING = {
    "anesthesia": "Anesthesiology",
    "anaesthesia": "Anesthesiology",
    "anesthesiology": "Anesthesiology",
    "general surgery": "General Surgery",
    "gen surgery": "General Surgery",
    "gynecology": "Gynecology",
    "gynaecology": "Gynecology",
    "obstetrics": "Obstetrics",
    "obg": "Obstetrics",
    "orthopedics": "Orthopedics",
    "orthopaedics": "Orthopedics",
    "urology": "Urology",
    "ent": "ENT",
    "neurosurgery": "Neurosurgery",
    "cardiac": "Cardiac Surgery",
    "cardiac surgery": "Cardiac Surgery",
    "cardiothoracic": "Cardiothoracic Surgery",
    "vascular": "Vascular Surgery",
    "gastro": "Gastroenterology",
    "gastroenterology": "Gastroenterology",
    "oncosurgery": "Oncosurgery",
    "oncology": "Oncosurgery",
    "ophthalmology": "Ophthalmology",
    "plastic": "Plastic Surgery",
    "plastic surgery": "Plastic Surgery",
    "dental": "Dental/Maxillofacial",
    "maxillofacial": "Dental/Maxillofacial",
    "pediatric": "Pediatric Surgery",
    "paediatric": "Pediatric Surgery",
    "transplant": "Transplant Surgery",
    "trauma": "Trauma Surgery",
    "interventional radiology": "Interventional Radiology",
    "ir": "Interventional Radiology",
}

INCIDENT_TYPE_MAPPING = {
    "airway": "Airway Event",
    "airway event": "Airway Event",
    "respiratory": "Respiratory Event",
    "respiratory event": "Respiratory Event",
    "cardiovascular": "Cardiovascular Event",
    "cardiovascular event": "Cardiovascular Event",
    "medication": "Medication Error",
    "medication error": "Medication Error",
    "drug error": "Medication Error",
    "equipment": "Equipment Failure",
    "equipment failure": "Equipment Failure",
    "communication": "Communication Failure",
    "communication failure": "Communication Failure",
    "procedure": "Procedure-Related",
    "procedure-related": "Procedure-Related",
    "positioning": "Positioning Injury",
    "positioning injury": "Positioning Injury",
    "documentation": "Documentation Error",
    "documentation error": "Documentation Error",
}

MONITORING_MAPPING = {
    "ecg": "ECG",
    "ekg": "ECG",
    "pulse oximeter": "Pulse Oximeter",
    "spo2": "Pulse Oximeter",
    "o2 sat": "Pulse Oximeter",
    "nibp": "NIBP",
    "nbp": "NIBP",
    "non invasive bp": "NIBP",
    "capnograph": "Capnograph",
    "etco2": "Capnograph",
    "temperature": "Temperature",
    "temp": "Temperature",
    "ibp": "Invasive BP",
    "invasive bp": "Invasive BP",
    "cvp": "CVP",
    "arterial line": "Arterial Line",
    "a-line": "Arterial Line",
    "urine output": "Urine Output",
    "neuromuscular": "Neuromuscular Monitor",
    "nmt": "Neuromuscular Monitor",
    "fio2": "FiO2",
    "fi o2": "FiO2",
    "respiratory rate": "Respiratory Rate",
    "rr": "Respiratory Rate",
    "st segment": "ST Segment",
    "bis": "BIS",
    "agm": "Other",
}


def map_sex(value: object) -> str | None:
    return normalize_choice(value, SEX_MAPPING)


def map_procedure_type(value: object) -> str | None:
    return normalize_choice(value, PROCEDURE_MAPPING)


def map_severity(value: object) -> str | None:
    return normalize_choice(value, SEVERITY_MAPPING)


def map_outcome_category(value: object) -> str | None:
    normalized = normalize_choice(value, OUTCOME_CATEGORY_MAPPING)
    if normalized is None:
        return None

    raw = str(normalized).strip().lower()
    if re.fullmatch(r"[abcde]\d+", raw):
        return raw[0].upper()
    return normalized


def map_surgical_branch(value: object) -> str | None:
    return normalize_choice(value, SURGICAL_BRANCH_MAPPING)


def map_incident_types(value: list[str] | str | None) -> list[str] | None:
    items = normalize_list_text(value)
    if not items:
        return None
    out: list[str] = []
    for item in items:
        mapped = normalize_choice(item, INCIDENT_TYPE_MAPPING)
        if mapped and mapped not in out:
            out.append(mapped)
    return out or None


def map_monitoring_list(value: list[str] | str | None) -> list[str] | None:
    items = normalize_list_text(value)
    if not items:
        return None
    out: list[str] = []
    for item in items:
        mapped = normalize_choice(item, MONITORING_MAPPING)
        if mapped and mapped not in out:
            out.append(mapped)
    return out or None


def missing_to_none(value: object) -> object | None:
    """Convert known missing tokens to None."""
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    if text.lower() in MISSING_TOKENS:
        return None
    return value


def normalize_bool(value: object) -> bool | None:
    """Normalize bool-like values into True/False/None."""
    value = missing_to_none(value)
    if value is None:
        return None

    text = str(value).strip().lower()
    if text in BOOLEAN_TRUE_TOKENS:
        return True
    if text in BOOLEAN_FALSE_TOKENS:
        return False
    return None


def normalize_text(value: object) -> str | None:
    """Normalize a free-text field with whitespace cleanup."""
    value = missing_to_none(value)
    if value is None:
        return None
    return normalize_whitespace(str(value))


def normalize_list_text(value: list[str] | str | None) -> list[str] | None:
    """Normalize a list of labels or comma/semicolon separated text."""
    if value is None:
        return None

    items: list[str]
    if isinstance(value, list):
        items = value
    else:
        raw = str(value)
        sep = "," if "," in raw else ";"
        items = raw.split(sep)

    out: list[str] = []
    for item in items:
        normalized = normalize_text(item)
        if normalized:
            out.append(normalized)

    return out or None


def normalize_choice(value: object, mapping: dict[str, str]) -> str | None:
    """Normalize text values through a case-insensitive mapping."""
    value = normalize_text(value)
    if value is None:
        return None

    key = value.lower()
    if key in mapping:
        return mapping[key]
    return value


def parse_date(value: object) -> datetime | None:
    """Parse dates from common input formats."""
    value = missing_to_none(value)
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
