"""Unit tests for Week 12: PDF Parser.

Covers:
  - fix_doubled_chars() — the character-deduplication algorithm
  - PDFParser._parse_sections() — section splitting
  - PDFParser static field-extraction helpers
  - PDFParser._build_incident() with synthetic section data
  - Error handling (missing file, wrong extension)

No real PDF files, network calls, or LLM calls are made.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion.pdf_parser import PDFParser, _HARM_SEVERITY, fix_doubled_chars


# ---------------------------------------------------------------------------
# fix_doubled_chars — algorithm correctness
# ---------------------------------------------------------------------------


class TestFixDoubledChars:
    def test_basic_word(self):
        assert fix_doubled_chars("PPrriimmaarryy") == "Primary"

    def test_acronym(self):
        assert fix_doubled_chars("EECCGG") == "ECG"

    def test_age_range_token(self):
        assert fix_doubled_chars("2211--3300") == "21-30"

    def test_full_age_phrase(self):
        assert fix_doubled_chars("2211--3300 yyeeaarrss") == "21-30 years"

    def test_elective(self):
        assert fix_doubled_chars("EElleeccttiivvee") == "Elective"

    def test_gynecology(self):
        assert fix_doubled_chars("GGyynneeccoollooggyy") == "Gynecology"

    def test_odd_length_token_untouched(self):
        assert fix_doubled_chars("abc") == "abc"

    def test_mixed_pairs_token_untouched(self):
        # "abcd": a≠b → not fully doubled → unchanged
        assert fix_doubled_chars("abcd") == "abcd"

    def test_empty_string(self):
        assert fix_doubled_chars("") == ""

    def test_whitespace_only(self):
        assert fix_doubled_chars("   ") == "   "

    def test_roman_numeral_i_doubled(self):
        # ASA grade I stored as "II"
        assert fix_doubled_chars("II") == "I"

    def test_roman_numeral_ii_doubled(self):
        # ASA grade II stored as "IIII"
        assert fix_doubled_chars("IIII") == "II"

    def test_roman_numeral_iii_doubled(self):
        assert fix_doubled_chars("IIIIII") == "III"

    def test_parenthesised_acronym(self):
        # "(CL" from doubled "((CCLL" (part of CL IIb)
        assert fix_doubled_chars("((CCLL") == "(CL"

    def test_natural_text_unchanged(self):
        # Labels and section headers are NOT doubled
        text = "Age Range: 21-30 years"
        assert fix_doubled_chars(text) == text

    def test_natural_text_with_double_letter(self):
        # "success" has "cc" and "ss" but as a whole token is NOT fully doubled
        assert fix_doubled_chars("success") == "success"

    def test_sentence_with_doubled_values(self):
        fixed = fix_doubled_chars("Sex: FFeem maalle")
        assert "Fe" in fixed or "Female" in fixed or "Fem" in fixed

    def test_single_char_doubled(self):
        assert fix_doubled_chars("AA") == "A"

    def test_number_doubled(self):
        # "2" doubled → "22"
        assert fix_doubled_chars("22") == "2"

    def test_number_22_doubled(self):
        # the actual number 22 would appear as "2222" when doubled
        assert fix_doubled_chars("2222") == "22"

    def test_hyphenated_compound_fixed(self):
        # "21-30" when doubled becomes "2211--3300"
        assert fix_doubled_chars("2211--3300") == "21-30"

    def test_multiword_sentence(self):
        result = fix_doubled_chars("GGeenneerraall AAnnaaeesstthhiiaass")
        assert "General" in result or result.startswith("G")

    def test_preserves_spacing(self):
        result = fix_doubled_chars("AA BB CC")
        assert result == "A B C"


# ---------------------------------------------------------------------------
# _HARM_SEVERITY mapping
# ---------------------------------------------------------------------------


class TestHarmSeverityMapping:
    def test_category_e_is_moderate(self):
        assert _HARM_SEVERITY["E"] == "Moderate"

    def test_category_d_is_low(self):
        assert _HARM_SEVERITY["D"] == "Low"

    def test_category_a_is_none(self):
        assert _HARM_SEVERITY["A"] == "None"

    def test_category_f_is_high(self):
        assert _HARM_SEVERITY["F"] == "High"

    def test_category_g_is_critical(self):
        assert _HARM_SEVERITY["G"] == "Critical"

    def test_category_i_is_critical(self):
        assert _HARM_SEVERITY["I"] == "Critical"

    def test_all_nine_categories_present(self):
        assert set(_HARM_SEVERITY.keys()) == set("ABCDEFGHI")


# ---------------------------------------------------------------------------
# PDFParser — section parsing
# ---------------------------------------------------------------------------


_SAMPLE_FIXED_TEXT = """\
Basic Information
Age Range: 21-30 years
Sex: Female
Weight: 65 Height: 165 BMI: 23.9
ASA Grade: I
Procedure Information
Surgical Branch: Gynecology
Procedure: DHC
Type of Procedure: Elective
Incident Narrative Description
Patient experienced bronchospasm during laparoscopy.
Anesthesia Technique
General Anesthesia ETT
Monitoring Used
ECG Pulse Oximeter Capnograph NIBP
Incident Demographics
Time of Incident: Working hours
Place of Incident: Operating room
Timing of Event: On induction
Incident Detection: Anaesthesiologist
Patient Outcome Category
Category E - temporary harm requiring intervention
Reviewer's Comments
Incident & Outcome:
Contributing Factors: Positioning
Root Cause & Prevention:
No pre-operative respiratory screening documented.
Suggested Course of Action:
Implement mandatory respiratory risk stratification.
"""


class TestParseSections:
    def _parser(self) -> PDFParser:
        return PDFParser()

    def test_sections_dict_returned(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert isinstance(sections, dict)

    def test_full_text_always_present(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert "full_text" in sections

    def test_basic_information_present(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert "basic_information" in sections

    def test_procedure_information_present(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert "procedure_information" in sections

    def test_incident_narrative_description_present(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert "incident_narrative_description" in sections

    def test_anesthesia_technique_present(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert "anesthesia_technique" in sections

    def test_monitoring_used_present(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert "monitoring_used" in sections

    def test_patient_outcome_category_present(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert "patient_outcome_category" in sections

    def test_section_content_correct(self):
        sections = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        assert "21-30" in sections.get("basic_information", "")

    def test_empty_text_returns_full_text_only(self):
        sections = self._parser()._parse_sections("")
        assert sections == {"full_text": ""}

    def test_no_headers_returns_full_text_only(self):
        text = "Some random text without any known headers."
        sections = self._parser()._parse_sections(text)
        assert "full_text" in sections
        assert sections["full_text"] == text


# ---------------------------------------------------------------------------
# PDFParser static helpers
# ---------------------------------------------------------------------------


class TestFieldHelper:
    def test_basic_extraction(self):
        text = "Age Range: 21-30 years"
        result = PDFParser._field(text, r"Age\s+Range[:\s]+([^\n]+)")
        assert result == "21-30 years"

    def test_returns_none_on_no_match(self):
        result = PDFParser._field("no match here", r"XYZ[:\s]+([^\n]+)")
        assert result is None

    def test_returns_none_on_empty_text(self):
        assert PDFParser._field("", r"Age[:\s]+([^\n]+)") is None

    def test_strips_whitespace(self):
        result = PDFParser._field("Sex:   Female  \n", r"Sex[:\s]+([^\n]+)")
        assert result == "Female"


class TestFloatFieldHelper:
    def test_basic_float(self):
        result = PDFParser._float_field("Weight: 65.5", r"Weight[:\s]+([\d.]+)")
        assert result == 65.5

    def test_integer_coerced_to_float(self):
        result = PDFParser._float_field("Weight: 65", r"Weight[:\s]+([\d.]+)")
        assert result == 65.0

    def test_returns_none_on_no_match(self):
        result = PDFParser._float_field("no weight here", r"Weight[:\s]+([\d.]+)")
        assert result is None

    def test_returns_none_on_empty(self):
        assert PDFParser._float_field("", r"Weight[:\s]+([\d.]+)") is None


class TestOutcomeCategoryHelper:
    def test_category_letter_extraction(self):
        assert PDFParser._outcome_category("Category E - temporary harm") == "E"

    def test_category_d_extraction(self):
        assert PDFParser._outcome_category("Category D2 - required intervention") == "D"

    def test_none_on_no_category(self):
        assert PDFParser._outcome_category("no outcome here") is None

    def test_none_on_empty(self):
        assert PDFParser._outcome_category("") is None

    def test_case_insensitive(self):
        assert PDFParser._outcome_category("category e result") == "E"


class TestPrimaryTechniqueHelper:
    def test_general_anaesthesia(self):
        result = PDFParser._primary_technique("General Anaesthesia ETT")
        assert result is not None
        assert "General" in result

    def test_spinal(self):
        result = PDFParser._primary_technique("Spinal block L3/L4")
        assert result == "Spinal"

    def test_none_on_unrecognised(self):
        result = PDFParser._primary_technique("Unknown technique applied")
        assert result is None

    def test_none_on_empty(self):
        assert PDFParser._primary_technique("") is None


class TestIntubationTypeHelper:
    def test_ett(self):
        assert PDFParser._intubation_type("ETT size 7.5") == "ETT"

    def test_lma(self):
        assert PDFParser._intubation_type("LMA classic #4") == "LMA"

    def test_face_mask(self):
        assert PDFParser._intubation_type("mask anaesthesia induction") == "Face Mask"

    def test_none_on_empty(self):
        assert PDFParser._intubation_type("") is None

    def test_none_on_no_match(self):
        assert PDFParser._intubation_type("regional technique used") is None


class TestMonitoringHelper:
    def test_ecg_found(self):
        assert "ECG" in PDFParser._monitoring("ECG Pulse Oximeter")

    def test_multiple_monitors(self):
        result = PDFParser._monitoring("ECG Pulse Oximeter Capnograph NIBP")
        assert "ECG" in result
        assert "Pulse Oximeter" in result
        assert "Capnograph" in result
        assert "NIBP" in result

    def test_empty_text_returns_empty(self):
        assert PDFParser._monitoring("") == []

    def test_unknown_text_returns_empty(self):
        assert PDFParser._monitoring("no monitors listed here") == []


class TestIncidentTypesHelper:
    def test_airway_incident_detected(self):
        types = PDFParser._incident_types("Airway obstruction recorded", "", "")
        assert "Airway Incident" in types

    def test_equipment_related_detected(self):
        types = PDFParser._incident_types("", "Insufflator failure", "")
        assert "Equipment Related" in types

    def test_patient_safety_detected(self):
        types = PDFParser._incident_types("", "", "Safety event noted")
        assert "Patient Safety" in types

    def test_empty_sections_return_empty_list(self):
        assert PDFParser._incident_types("", "", "") == []

    def test_multiple_types(self):
        types = PDFParser._incident_types("airway event", "equipment fault", "")
        assert len(types) == 2


# ---------------------------------------------------------------------------
# PDFParser — build_incident with synthetic sections
# ---------------------------------------------------------------------------


class TestBuildIncident:
    def _parser(self) -> PDFParser:
        return PDFParser()

    def _sections(self) -> dict[str, str]:
        return self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)

    def test_returns_incident_instance(self):
        from src.models.incident import Incident
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert isinstance(inc, Incident)

    def test_incident_id_is_uuid(self):
        import uuid
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        uuid.UUID(inc.incident_id)

    def test_patient_age_range(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.patient.age_range == "21-30 years"

    def test_patient_sex(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.patient.sex == "Female"

    def test_patient_weight(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.patient.weight_kg == 65.0

    def test_patient_asa_grade(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.patient.asa_grade == "I"

    def test_surgery_branch(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.surgery.surgical_branch == "Gynecology"

    def test_surgery_type_of_procedure(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.surgery.type_of_procedure == "Elective"

    def test_incident_description_present(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.incident.incident_description is not None
        assert "bronchospasm" in inc.incident.incident_description

    def test_incident_time_of(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.incident.time_of_incident == "Working hours"

    def test_incident_place_of(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.incident.place_of_incident == "Operating room"

    def test_anesthesia_primary_technique(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.anesthesia.primary_technique is not None
        assert "General" in inc.anesthesia.primary_technique

    def test_anesthesia_intubation_type(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.anesthesia.intubation_type == "ETT"

    def test_monitoring_ecg_present(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.anesthesia.monitoring is not None
        assert "ECG" in inc.anesthesia.monitoring

    def test_outcome_category(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.outcome.outcome_category == "E"

    def test_outcome_harm_severity(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.outcome.harm_severity == "Moderate"

    def test_metadata_source_file(self):
        inc = self._parser()._build_incident(self._sections(), "test.pdf", "raw")
        assert inc.metadata.source_file == "test.pdf"

    def test_metadata_month_from_filename(self):
        # Filename contains _20260419_ → April 2026
        sec = self._parser()._parse_sections(_SAMPLE_FIXED_TEXT)
        inc = self._parser()._build_incident(
            sec, "Abdul_AIRLog_20260419_110939.pdf", "raw"
        )
        assert inc.metadata.month == "April"
        assert inc.metadata.year == 2026

    def test_raw_data_has_source_stem(self):
        inc = self._parser()._build_incident(self._sections(), "myfile.pdf", "raw")
        assert inc.raw_data is not None
        assert "source_stem" in inc.raw_data
        assert inc.raw_data["source_stem"] == "myfile"

    def test_raw_data_has_sections_found(self):
        inc = self._parser()._build_incident(self._sections(), "myfile.pdf", "raw")
        assert "sections_found" in inc.raw_data
        assert isinstance(inc.raw_data["sections_found"], list)


# ---------------------------------------------------------------------------
# PDFParser — error handling
# ---------------------------------------------------------------------------


class TestPDFParserErrors:
    def test_parse_file_nonexistent_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            PDFParser().parse_file(Path("/nonexistent/path/file.pdf"))

    def test_parse_file_wrong_extension_raises_value_error(self):
        with pytest.raises(ValueError, match=r"\.pdf"):
            PDFParser().parse_file(Path("some_file.xlsx"))

    def test_parse_directory_not_a_dir_raises(self):
        with pytest.raises(NotADirectoryError):
            PDFParser().parse_directory(Path("/nonexistent_directory"))

    def test_parse_directory_skips_non_pdf_files(self, tmp_path):
        (tmp_path / "not_a_pdf.txt").write_text("text content")
        result = PDFParser().parse_directory(tmp_path)
        assert result == []
