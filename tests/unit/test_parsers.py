"""Unit tests for Excel parser."""

from pathlib import Path

import pandas as pd
import pytest

from src.ingestion.excel_parser import ExcelParser
from src.models.incident import Incident


class TestExcelParser:
    """Tests for ExcelParser class."""

    @pytest.fixture
    def parser(self) -> ExcelParser:
        """Create a parser instance."""
        return ExcelParser()

    def test_parser_initialization(self, parser: ExcelParser):
        """Test parser initialization."""
        assert parser is not None
        assert hasattr(parser, "PATIENT_COLUMNS")
        assert hasattr(parser, "SURGERY_COLUMNS")

    def test_get_column_success(self, parser: ExcelParser):
        """Test _get_column method with valid data."""
        row = {"Age Range": "21-30 years"}
        value = parser._get_column(row, ["Age Range"])

        assert value == "21-30 years"

    def test_get_column_fallback(self, parser: ExcelParser):
        """Test _get_column method with fallback names."""
        row = {"age_range": "31-40 years"}
        value = parser._get_column(row, ["Age Range", "age_range", "AGE RANGE"])

        assert value == "31-40 years"

    def test_get_column_none(self, parser: ExcelParser):
        """Test _get_column method with missing column."""
        row = {"Other": "value"}
        value = parser._get_column(row, ["Age Range", "age_range"])

        assert value is None

    def test_get_column_nan(self, parser: ExcelParser):
        """Test _get_column method with NaN value."""
        row = {"Age Range": float("nan")}
        value = parser._get_column(row, ["Age Range"])

        assert value is None

    def test_get_column_empty_string(self, parser: ExcelParser):
        """Test _get_column method with empty string."""
        row = {"Age Range": ""}
        value = parser._get_column(row, ["Age Range"])

        assert value is None

    def test_get_numeric_success(self, parser: ExcelParser):
        """Test _get_numeric method."""
        row = {"Weight": 65.5}
        value = parser._get_numeric(row, ["Weight"])

        assert value == 65.5
        assert isinstance(value, float)

    def test_get_numeric_string(self, parser: ExcelParser):
        """Test _get_numeric with string value."""
        row = {"Weight": "75"}
        value = parser._get_numeric(row, ["Weight"])

        assert value == 75.0

    def test_get_numeric_none(self, parser: ExcelParser):
        """Test _get_numeric with missing column."""
        row = {"Other": "value"}
        value = parser._get_numeric(row, ["Weight"])

        assert value is None

    def test_get_numeric_nan(self, parser: ExcelParser):
        """Test _get_numeric with NaN."""
        row = {"Weight": float("nan")}
        value = parser._get_numeric(row, ["Weight"])

        assert value is None

    def test_parse_patient(self, parser: ExcelParser):
        """Test _parse_patient method."""
        row = {
            "Age Range": "21-30 years",
            "Sex": "Female",
            "Weight": 65.0,
            "Height": 165,
            "ASA Grade": "I",
        }

        patient = parser._parse_patient(row)

        assert patient.age_range == "21-30 years"
        assert patient.sex == "Female"
        assert patient.weight_kg == 65.0
        assert patient.height_cm == 165
        assert patient.asa_grade == "I"

    def test_parse_surgery(self, parser: ExcelParser):
        """Test _parse_surgery method."""
        row = {
            "Type of Procedure": "Elective",
            "Surgical Branch": "Gynecology",
            "Procedure": "DHC",
        }

        surgery = parser._parse_surgery(row)

        assert surgery.type_of_procedure == "Elective"
        assert surgery.surgical_branch == "Gynecology"
        assert surgery.procedure == "DHC"

    def test_parse_incident(self, parser: ExcelParser):
        """Test _parse_incident method."""
        row = {
            "Incident Narrative Description": "Insufflator malfunction",
            "Describe Incident": "Equipment failed",
            "Time of Incident": "Working hours",
            "Place of Incident": "Operating room",
            "Timing of Event": "On induction",
        }

        incident = parser._parse_incident(row)

        assert incident.incident_description == "Insufflator malfunction"
        assert incident.incident_details == "Equipment failed"
        assert incident.time_of_incident == "Working hours"

    def test_parse_row(self, parser: ExcelParser, sample_excel_dataframe: pd.DataFrame):
        """Test _parse_row method."""
        row = sample_excel_dataframe.iloc[0]
        headers = list(sample_excel_dataframe.columns)
        # parser expects (row_values_list, headers, source_file)
        incident = parser._parse_row(row.values.tolist(), headers, "test.xlsx")

        assert isinstance(incident, Incident)
        assert incident.incident_id is not None
        assert incident.patient.age_range == "21-30 years"
        assert incident.surgery.surgical_branch == "Gynecology"

    def test_validate_schema_valid(self, parser: ExcelParser, sample_excel_dataframe: pd.DataFrame):
        """Test validate_schema with valid data."""
        results = parser.validate_schema(sample_excel_dataframe)

        assert results["column_count"] == len(sample_excel_dataframe.columns)
        assert results["row_count"] == len(sample_excel_dataframe)

    def test_validate_schema_empty(self, parser: ExcelParser):
        """Test validate_schema with empty dataframe."""
        df = pd.DataFrame()
        results = parser.validate_schema(df)

        assert results["column_count"] == 0
        assert results["row_count"] == 0

    def test_parse_dataframe(self, parser: ExcelParser, sample_excel_dataframe: pd.DataFrame):
        """Test parsing a full dataframe."""
        # Create a temporary CSV file
        import tempfile

        # Create CSV with two header rows to match parser expectations (grouped header + sub-header)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name
        # Write two header rows (duplicate headers) then data rows
        with open(temp_path, "w", newline="", encoding="utf-8") as fh:
            # first header row (can be group headings or repeated headers)
            fh.write(",".join(list(sample_excel_dataframe.columns)) + "\n"
            )
            # second header row (effective sub-headers)
            fh.write(",".join(list(sample_excel_dataframe.columns)) + "\n"
            )
            sample_excel_dataframe.to_csv(fh, index=False, header=False)

        try:
            incidents = parser.parse_file(Path(temp_path))

            assert len(incidents) == len(sample_excel_dataframe)
            assert all(isinstance(i, Incident) for i in incidents)
            assert all(i.incident_id for i in incidents)
        finally:
            Path(temp_path).unlink()  # Clean up

    def test_parse_file_not_found(self, parser: ExcelParser):
        """Test parse_file with non-existent file."""
        with pytest.raises(FileNotFoundError):
            parser.parse_file(Path("non_existent.xlsx"))

    def test_parse_file_invalid_format(self, parser: ExcelParser):
        """Test parse_file with invalid file format."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                parser.parse_file(Path(temp_path))
        finally:
            Path(temp_path).unlink()

    def test_parse_with_missing_values(self, parser: ExcelParser):
        """Test parsing with missing values."""
        data = {
            "Age Range": ["21-30 years", None],
            "Sex": ["Female", "Male"],
            "Weight": [65.0, None],
            "Type of Procedure": ["Elective", "Emergency"],
        }
        df = pd.DataFrame(data)

        import tempfile

        # Create CSV with two header rows so parser picks the second as effective headers
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name
        with open(temp_path, "w", newline="", encoding="utf-8") as fh:
            fh.write(",".join(list(df.columns)) + "\n")
            fh.write(",".join(list(df.columns)) + "\n")
            df.to_csv(fh, index=False, header=False)

        try:
            incidents = parser.parse_file(Path(temp_path))

            # Check that missing values are handled
            assert incidents[0].patient.age_range == "21-30 years"
            assert incidents[1].patient.age_range is None
        finally:
            Path(temp_path).unlink()

    def test_parse_with_extra_whitespace(self, parser: ExcelParser):
        """Test parsing with extra whitespace."""
        row = {
            "Incident Narrative Description": "  Insufflator   malfunction  ",
        }

        incident = parser._parse_incident(row)

        # Should be normalized
        assert incident.incident_description == "Insufflator malfunction"

    def test_parse_medication_error_present(self, parser: ExcelParser):
        """Test parsing when medication error is present."""
        row = {
            "Type of Medication Error": "Wrong drug",
            "Cause of Medication Error": "Labeling failure",
        }

        error = parser._parse_medication_error(row)

        assert error is not None
        assert error.type_of_error == "Wrong drug"

    def test_parse_medication_error_absent(self, parser: ExcelParser):
        """Test parsing when medication error is absent."""
        row = {}

        error = parser._parse_medication_error(row)

        assert error is None


class TestExcelParserIntegration:
    """Integration tests for ExcelParser."""

    def test_full_parsing_workflow(self, sample_excel_dataframe: pd.DataFrame):
        """Test full parsing workflow."""
        import tempfile

        parser = ExcelParser()

        # Create temporary file
        # Write CSV with two header rows to match parser expectations
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name
        with open(temp_path, "w", newline="", encoding="utf-8") as fh:
            fh.write(",".join(list(sample_excel_dataframe.columns)) + "\n")
            fh.write(",".join(list(sample_excel_dataframe.columns)) + "\n")
            sample_excel_dataframe.to_csv(fh, index=False, header=False)

        try:
            # Parse file
            incidents = parser.parse_file(Path(temp_path))

            # Validate results
            assert len(incidents) > 0
            for incident in incidents:
                assert incident.incident_id
                assert incident.patient
                assert incident.surgery
                assert incident.outcome
                assert incident.metadata.source_file == Path(temp_path).name
        finally:
            Path(temp_path).unlink()

    def test_parsing_with_schema_validation(self, sample_excel_dataframe: pd.DataFrame):
        """Test parsing with schema validation."""
        parser = ExcelParser()

        # Validate schema
        results = parser.validate_schema(sample_excel_dataframe)
        assert results["column_count"] > 0

        # Parse successfully
        import tempfile

        # Write CSV with two header rows to match parser expectations
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            temp_path = f.name
        with open(temp_path, "w", newline="", encoding="utf-8") as fh:
            fh.write(",".join(list(sample_excel_dataframe.columns)) + "\n")
            fh.write(",".join(list(sample_excel_dataframe.columns)) + "\n")
            sample_excel_dataframe.to_csv(fh, index=False, header=False)

        try:
            incidents = parser.parse_file(Path(temp_path))
            assert len(incidents) == len(sample_excel_dataframe)
        finally:
            Path(temp_path).unlink()
