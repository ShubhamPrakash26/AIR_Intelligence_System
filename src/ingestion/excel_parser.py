"""Excel file parser for AIR incident logs."""

from pathlib import Path
from typing import Any

import pandas as pd

from src.models.incident import (
    AnesthesiaTechnique,
    ContextMetadata,
    Incident,
    IncidentDetails,
    MedicationError,
    OutcomeInfo,
    PatientInfo,
    SurgeryInfo,
)
from src.utils.helpers import generate_incident_id, normalize_whitespace
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ExcelParser:
    """
    Parser for Excel incident logs.

    Handles .xlsx, .xls, and .csv files containing AIR incident data.
    """

    # Expected column mappings - AIR incident form standard format
    PATIENT_COLUMNS = {
        "age_range": ["Patient Age", "Age Range", "age_range", "AGE RANGE"],
        "sex": ["Patient Sex", "Sex", "sex", "SEX"],
        "weight_kg": ["Weight", "weight", "WEIGHT", "Weight (kg)"],
        "height_cm": ["Height", "height", "HEIGHT", "Height (cm)"],
        "bmi": ["BMI", "bmi"],
        "asa_grade": ["ASA Grade", "asa_grade", "ASA GRADE"],
    }

    SURGERY_COLUMNS = {
        "type_of_procedure": ["Type of Surgery", "Type of Procedure", "type_of_procedure", "TYPE OF PROCEDURE"],
        "surgical_branch": ["Surgical Branch", "surgical_branch", "SURGICAL BRANCH"],
        "procedure": ["Surgical Procedure", "Procedure", "procedure", "PROCEDURE"],
    }

    INCIDENT_COLUMNS = {
        "incident_description": [
            "Incident Description",
            "Incident Narrative Description",
            "incident_narrative_description",
            "INCIDENT NARRATIVE DESCRIPTION",
        ],
        "incident_details": ["Describe Incident", "describe_incident", "DESCRIBE INCIDENT"],
        "time_of_incident": ["Time of Incident", "time_of_incident", "TIME OF INCIDENT"],
        "place_of_incident": ["Place of Incident", "place_of_incident", "PLACE OF INCIDENT"],
        "timing_of_event": ["Timing of Event", "timing_of_event", "TIMING OF EVENT"],
        "incident_detection": ["Incident Detection", "incident_detection", "INCIDENT DETECTION"],
        "incident_relation": ["Incident Relation", "incident_relation", "INCIDENT RELATION"],
    }

    ANESTHESIA_COLUMNS = {
        "primary_technique": ["Primary Technique", "Primary", "primary_technique", "PRIMARY TECHNIQUE"],
        "supplementary_technique": ["Supplementary Technique", "supplementary_technique", "SUPPLEMENTARY TECHNIQUE"],
        "monitoring": ["Monitoring", "monitoring", "MONITORING"],
        "intubation_type": ["ETT", "Intubation Type", "intubation_type"],
    }

    OUTCOME_COLUMNS = {
        "outcome_category": ["Patient Outcome Category", "outcome_category", "OUTCOME CATEGORY"],
        "morbidity": ["Morbidity", "morbidity", "MORBIDITY"],
        "patient_safety": ["Patient Safety", "patient_safety", "PATIENT SAFETY"],
        "personnel_safety": ["Personnel Safety", "personnel_safety", "PERSONNEL SAFETY"],
        "patient_satisfaction": ["Patient Satisfaction", "patient_satisfaction", "PATIENT SATISFACTION"],
        "harm_severity": ["Harm Severity", "harm_severity", "HARM SEVERITY"],
    }

    def __init__(self):
        """Initialize the parser."""
        logger.info("Initializing ExcelParser")
        # column map will be set per-file when headers are known
        self.column_map: dict[str, int] = {}
        self.headers: list[str | None] = []

    def parse_file(self, file_path: Path) -> list[Incident]:
        """
        Parse an Excel file and return list of Incident objects.

        The file is expected to have headers in the first row, with data starting from row 2.

        Args:
            file_path: Path to Excel file

        Returns:
            List of parsed Incident objects

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is not supported
            Exception: If parsing fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Determine file type
        suffix = file_path.suffix.lower()
        if suffix not in [".xlsx", ".xls", ".csv"]:
            raise ValueError(f"Unsupported file format: {suffix}")

        logger.info(f"Parsing file: {file_path}")

        try:
            # Load file without headers.
            # AIR form layout uses two header rows: grouped headings (row 0),
            # then sub-column labels (row 1). Data begins at row 2.
            if suffix == ".csv":
                df = pd.read_csv(file_path, header=None)
            else:
                df = pd.read_excel(file_path, header=None)

            # Read the two header rows
            header_row_0 = df.iloc[0].values.tolist() if len(df) > 0 else []
            header_row_1 = df.iloc[1].values.tolist() if len(df) > 1 else []

            # Build effective headers: prefer second-row (sub-heading), fallback to first-row
            headers: list[str | None] = []
            max_len = max(len(header_row_0), len(header_row_1))
            for i in range(max_len):
                h0 = header_row_0[i] if i < len(header_row_0) else None
                h1 = header_row_1[i] if i < len(header_row_1) else None
                if pd.isna(h1) or str(h1).strip() == "":
                    if pd.isna(h0) or str(h0).strip() == "":
                        headers.append(None)
                    else:
                        headers.append(str(h0).strip())
                else:
                    headers.append(str(h1).strip())

            # Build column index map for lookup
            self._build_column_map(headers)

            # Data starts from row index 2
            data_start = 2 if len(df) > 2 else len(df)
            df_data = df.iloc[data_start:].reset_index(drop=True)

            logger.info(f"Loaded {len(df_data)} rows from {file_path.name}")

            # Parse rows
            incidents: list[Incident] = []
            for idx, row in df_data.iterrows():
                try:
                    incident = self._parse_row(row.values.tolist(), headers, file_path.name)
                    incidents.append(incident)
                except Exception as e:
                    logger.error(f"Error parsing row {idx}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(incidents)}/{len(df_data)} incidents")
            return incidents

        except Exception as e:
            logger.error(f"Failed to parse file {file_path}: {e}")
            raise

    def _parse_row(self, row_values: list, headers: list, source_file: str) -> Incident:
        """
        Parse a single row into an Incident object.

        Args:
            row_values: List/array of row values
            headers: List of header names
            source_file: Name of source file

        Returns:
            Parsed Incident object
        """
        # Create a dictionary mapping header names to row values
        row_dict = {}
        for header, value in zip(headers, row_values):
            # Use header index as key if header is NaN, otherwise use header name
            if pd.isna(header):
                key = f"col_{len([k for k in row_dict.keys() if str(k).startswith('col_')])}"
            else:
                key = str(header).strip()
            
            row_dict[key] = value

        # Generate incident ID
        incident_id = generate_incident_id()

        # Parse each section
        patient = self._parse_patient(row_dict)
        surgery = self._parse_surgery(row_dict)
        incident_details = self._parse_incident(row_dict)
        anesthesia = self._parse_anesthesia(row_dict)
        medication_error = self._parse_medication_error(row_dict)
        outcome = self._parse_outcome(row_dict)
        metadata = ContextMetadata(source_file=source_file)

        # Clean raw_data: convert NaN to None and keep string values
        cleaned_raw_data = {}
        for key, value in row_dict.items():
            if pd.isna(value):
                cleaned_raw_data[key] = None
            else:
                cleaned_raw_data[key] = str(value) if value is not None else None

        # Create and return Incident
        incident = Incident(
            incident_id=incident_id,
            patient=patient,
            surgery=surgery,
            incident=incident_details,
            anesthesia=anesthesia,
            medication_error=medication_error,
            outcome=outcome,
            metadata=metadata,
            raw_data=cleaned_raw_data,
        )

        return incident

    def _parse_patient(self, row: dict[str, Any]) -> PatientInfo:
        """Parse patient information from row."""
        return PatientInfo(
            age_range=self._get_column(row, self.PATIENT_COLUMNS["age_range"]),
            sex=self._get_column(row, self.PATIENT_COLUMNS["sex"]),
            weight_kg=self._get_numeric(row, self.PATIENT_COLUMNS["weight_kg"]),
            height_cm=self._get_numeric(row, self.PATIENT_COLUMNS["height_cm"]),
            bmi=self._get_numeric(row, self.PATIENT_COLUMNS["bmi"]),
            asa_grade=self._get_column(row, self.PATIENT_COLUMNS["asa_grade"]),
        )

    def _parse_surgery(self, row: dict[str, Any]) -> SurgeryInfo:
        """Parse surgery information from row."""
        return SurgeryInfo(
            type_of_procedure=self._get_column(row, self.SURGERY_COLUMNS["type_of_procedure"]),
            surgical_branch=self._get_column(row, self.SURGERY_COLUMNS["surgical_branch"]),
            procedure=self._get_column(row, self.SURGERY_COLUMNS["procedure"]),
        )

    def _parse_incident(self, row: dict[str, Any]) -> IncidentDetails:
        """Parse incident details from row."""
        return IncidentDetails(
            incident_description=normalize_whitespace(
                self._get_column(row, self.INCIDENT_COLUMNS["incident_description"])
            ),
            incident_details=normalize_whitespace(
                self._get_column(row, self.INCIDENT_COLUMNS["incident_details"])
            ),
            time_of_incident=self._get_column(row, self.INCIDENT_COLUMNS["time_of_incident"]),
            place_of_incident=self._get_column(row, self.INCIDENT_COLUMNS["place_of_incident"]),
            timing_of_event=self._get_column(row, self.INCIDENT_COLUMNS["timing_of_event"]),
            incident_detection=self._get_column(row, self.INCIDENT_COLUMNS["incident_detection"]),
            incident_relation=self._get_column(row, self.INCIDENT_COLUMNS.get("incident_relation", [])),
        )

    def _parse_anesthesia(self, row: dict[str, Any]) -> AnesthesiaTechnique:
        """Parse anesthesia technique from row."""
        def to_list(val: str | list | None) -> list[str] | None:
            if val is None:
                return None
            if isinstance(val, list):
                return [str(v).strip() for v in val if v is not None and str(v).strip()]
            # split comma/semicolon separated strings
            try:
                s = str(val)
            except Exception:
                return None
            parts = [p.strip() for p in s.split(",") if p.strip()]
            if not parts:
                parts = [p.strip() for p in s.split(";") if p.strip()]
            return parts if parts else None

        primary = self._get_column(row, self.ANESTHESIA_COLUMNS["primary_technique"])
        supplementary = self._get_column(row, self.ANESTHESIA_COLUMNS["supplementary_technique"])
        monitoring_raw = self._get_column(row, self.ANESTHESIA_COLUMNS["monitoring"])
        return AnesthesiaTechnique(
            primary_technique=primary,
            supplementary_technique=to_list(supplementary),
            monitoring=to_list(monitoring_raw),
            intubation_type=self._get_column(row, self.ANESTHESIA_COLUMNS["intubation_type"]),
        )

    def _parse_medication_error(self, row: dict[str, Any]) -> MedicationError | None:
        """Parse medication error information from row."""
        # Check if any medication error columns are present
        error_type = self._get_column(row, ["Type of Medication Error"])
        if error_type:
            return MedicationError(
                type_of_error=error_type,
                cause_of_error=self._get_column(row, ["Cause of Medication Error"]),
            )
        return None

    def _parse_outcome(self, row: dict[str, Any]) -> OutcomeInfo:
        """Parse outcome information from row."""
        return OutcomeInfo(
            outcome_category=self._get_column(row, self.OUTCOME_COLUMNS["outcome_category"]),
            morbidity=self._get_column(row, self.OUTCOME_COLUMNS["morbidity"]),
            patient_safety=self._get_column(row, self.OUTCOME_COLUMNS["patient_safety"]),
            personnel_safety=self._get_column(row, self.OUTCOME_COLUMNS["personnel_safety"]),
            patient_satisfaction=self._get_column(row, self.OUTCOME_COLUMNS["patient_satisfaction"]),
            harm_severity=self._get_column(row, self.OUTCOME_COLUMNS["harm_severity"]),
        )

    def _build_column_map(self, headers: list[str | None]) -> None:
        """
        Build a map of normalized header -> column index for quick lookups.

        Args:
            headers: List of header names (may contain None)
        """
        self.column_map = {}
        self.headers = headers
        for idx, h in enumerate(headers):
            if h is None:
                continue
            try:
                key = normalize_whitespace(str(h)).lower()
            except Exception:
                key = str(h).strip().lower()
            self.column_map[key] = idx

    @staticmethod
    def _get_column(row: dict[str, Any], possible_names: list[str]) -> str | None:
        """
        Get column value by trying multiple possible names.

        Args:
            row: Row dictionary
            possible_names: List of possible column names

        Returns:
            Column value or None
        """
        # Normalize row keys for case-insensitive matching
        normalized_row_keys: dict[str, str] = {}
        for k in row.keys():
            try:
                nk = normalize_whitespace(str(k)).lower()
            except Exception:
                nk = str(k).strip().lower()
            normalized_row_keys[nk] = k

        for name in possible_names:
            try:
                target = normalize_whitespace(str(name)).lower()
            except Exception:
                target = str(name).strip().lower()
            if target in normalized_row_keys:
                original_key = normalized_row_keys[target]
                value = row.get(original_key)
                if pd.isna(value) or value == "":
                    return None
                return str(value).strip()
        return None

    @staticmethod
    def _get_numeric(row: dict[str, Any], possible_names: list[str]) -> float | None:
        """
        Get numeric column value by trying multiple possible names.

        Args:
            row: Row dictionary
            possible_names: List of possible column names

        Returns:
            Numeric value or None
        """
        # Normalize row keys for case-insensitive matching
        normalized_row_keys: dict[str, str] = {}
        for k in row.keys():
            try:
                nk = normalize_whitespace(str(k)).lower()
            except Exception:
                nk = str(k).strip().lower()
            normalized_row_keys[nk] = k

        for name in possible_names:
            try:
                target = normalize_whitespace(str(name)).lower()
            except Exception:
                target = str(name).strip().lower()
            if target in normalized_row_keys:
                original_key = normalized_row_keys[target]
                value = row.get(original_key)
                if pd.isna(value):
                    return None
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return None
        return None

    def validate_schema(self, df: pd.DataFrame) -> dict[str, Any]:
        """
        Validate DataFrame schema against expected columns.

        Args:
            df: DataFrame to validate

        Returns:
            Dictionary with validation results
        """
        results = {
            "is_valid": True,
            "missing_columns": [],
            "unexpected_columns": [],
            "column_count": len(df.columns),
            "row_count": len(df),
        }

        # Check for expected columns
        all_expected = set()
        for col_list in (
            list(self.PATIENT_COLUMNS.values())
            + list(self.SURGERY_COLUMNS.values())
            + list(self.INCIDENT_COLUMNS.values())
            + list(self.ANESTHESIA_COLUMNS.values())
            + list(self.OUTCOME_COLUMNS.values())
        ):
            all_expected.update(col_list)

        df_columns = set(df.columns)

        # Check if at least some expected columns are present
        if not any(col in df_columns for col in all_expected):
            results["is_valid"] = False
            results["missing_columns"] = list(all_expected)

        logger.info(f"Schema validation: {results}")
        return results
