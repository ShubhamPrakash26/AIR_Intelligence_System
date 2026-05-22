"""Standard enums and canonical value sets for normalization."""

from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "Low"
    MODERATE = "Moderate"
    HIGH = "High"
    CRITICAL = "Critical"


class IncidentType(str, Enum):
    AIRWAY = "Airway Event"
    RESPIRATORY = "Respiratory Event"
    CARDIOVASCULAR = "Cardiovascular Event"
    MEDICATION = "Medication Error"
    EQUIPMENT = "Equipment Failure"
    COMMUNICATION = "Communication Failure"
    PROCEDURE = "Procedure-Related"
    POSITIONING = "Positioning Injury"
    DOCUMENTATION = "Documentation Error"
    OTHER = "Other"


class ProcedureType(str, Enum):
    ELECTIVE = "Elective"
    EMERGENCY = "Emergency"


class SurgicalBranch(str, Enum):
    ANESTHESIA = "Anesthesiology"
    GENERAL_SURGERY = "General Surgery"
    GYNECOLOGY = "Gynecology"
    OBSTETRICS = "Obstetrics"
    ORTHOPEDICS = "Orthopedics"
    UROLOGY = "Urology"
    ENT = "ENT"
    NEUROSURGERY = "Neurosurgery"
    CARDIAC = "Cardiac Surgery"
    CARDIOTHORACIC = "Cardiothoracic Surgery"
    VASCULAR = "Vascular Surgery"
    GASTROENTEROLOGY = "Gastroenterology"
    ONCOLOGY = "Oncosurgery"
    OPHTHALMOLOGY = "Ophthalmology"
    PLASTIC = "Plastic Surgery"
    DENTAL_MAXILLOFACIAL = "Dental/Maxillofacial"
    PEDIATRIC = "Pediatric Surgery"
    TRANSPLANT = "Transplant Surgery"
    TRAUMA = "Trauma Surgery"
    INTERVENTIONAL_RADIOLOGY = "Interventional Radiology"
    OTHER = "Other"


class SexType(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    OTHER = "Other"
    UNKNOWN = "Unknown"


class OutcomeCategory(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"


class MonitoringType(str, Enum):
    ECG = "ECG"
    SPO2 = "Pulse Oximeter"
    NIBP = "NIBP"
    ETCO2 = "Capnograph"
    TEMPERATURE = "Temperature"
    INVASIVE_BP = "Invasive BP"
    CVP = "CVP"
    ARTERIAL_LINE = "Arterial Line"
    URINE_OUTPUT = "Urine Output"
    NEUROMUSCULAR = "Neuromuscular Monitor"
    FIO2 = "FiO2"
    RESPIRATORY_RATE = "Respiratory Rate"
    ST_SEGMENT = "ST Segment"
    BIS = "BIS"
    OTHER = "Other"


MISSING_TOKENS = {
    "",
    "-",
    "--",
    "na",
    "n/a",
    "none",
    "null",
    "nan",
    "not available",
}


BOOLEAN_TRUE_TOKENS = {"yes", "y", "true", "t", "1", "present"}
BOOLEAN_FALSE_TOKENS = {"no", "n", "false", "f", "0", "absent"}
