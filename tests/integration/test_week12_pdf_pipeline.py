"""Integration tests for Week 12: PDF Ingestion with real AIR Log PDFs.

Uses the three actual PDF files in data/inputs/pdf/.
No LLM or Qdrant calls are made — only the PDFParser and the pipeline
model-level validation for POST /pipeline/ingest/pdf are tested here.

The PDFs are:
  Abdul Nasser_AIRLog_20260419_110939.pdf  (equipment failure, Gynecology, Cat E)
  Abdul Nasser_AIRLog_20260419_111045.pdf  (retained throat pack, Neurosurgery)
  Abdul Nasser_AIRLog_20260419_111120.pdf  (difficult intubation, Vascular/Ortho, Cat D)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ingestion.pdf_parser import PDFParser, fix_doubled_chars
from src.models.incident import Incident

PDF_DIR = Path(__file__).parent.parent.parent / "data" / "inputs" / "pdf"

PDF_110939 = PDF_DIR / "Abdul Nasser_AIRLog_20260419_110939.pdf"
PDF_111045 = PDF_DIR / "Abdul Nasser_AIRLog_20260419_111045.pdf"
PDF_111120 = PDF_DIR / "Abdul Nasser_AIRLog_20260419_111120.pdf"

_ALL_PDFS = [PDF_110939, PDF_111045, PDF_111120]


# ---------------------------------------------------------------------------
# File presence guards
# ---------------------------------------------------------------------------


class TestPDFFilesExist:
    def test_110939_exists(self):
        assert PDF_110939.exists(), f"Missing test PDF: {PDF_110939}"

    def test_111045_exists(self):
        assert PDF_111045.exists(), f"Missing test PDF: {PDF_111045}"

    def test_111120_exists(self):
        assert PDF_111120.exists(), f"Missing test PDF: {PDF_111120}"


# ---------------------------------------------------------------------------
# Per-file parsing
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not all(p.exists() for p in _ALL_PDFS),
    reason="One or more test PDFs not found in data/inputs/pdf/",
)
class TestParsePDF110939:
    """Equipment failure — insufflator malfunction, Gynecology, Elective, Category E."""

    def _incident(self) -> Incident:
        result = PDFParser().parse_file(PDF_110939)
        assert result, "Parser returned empty list for 110939"
        return result[0]

    def test_returns_single_incident(self):
        result = PDFParser().parse_file(PDF_110939)
        assert len(result) == 1

    def test_incident_id_is_set(self):
        import uuid
        inc = self._incident()
        uuid.UUID(inc.incident_id)

    def test_source_file_recorded(self):
        inc = self._incident()
        assert inc.metadata.source_file is not None
        assert "110939" in inc.metadata.source_file

    def test_metadata_year(self):
        inc = self._incident()
        assert inc.metadata.year == 2026

    def test_metadata_month_april(self):
        inc = self._incident()
        assert inc.metadata.month == "April"

    def test_surgical_branch_or_procedure_present(self):
        inc = self._incident()
        assert (
            inc.surgery.surgical_branch is not None
            or inc.surgery.procedure is not None
        ), "Neither surgical_branch nor procedure was extracted"

    def test_outcome_category_present(self):
        inc = self._incident()
        assert inc.outcome.outcome_category is not None

    def test_harm_severity_present(self):
        inc = self._incident()
        assert inc.outcome.harm_severity is not None

    def test_raw_data_has_source_stem(self):
        inc = self._incident()
        assert inc.raw_data is not None
        assert "source_stem" in inc.raw_data


@pytest.mark.skipif(
    not all(p.exists() for p in _ALL_PDFS),
    reason="One or more test PDFs not found in data/inputs/pdf/",
)
class TestParsePDF111045:
    """Retained throat pack, Neurosurgery."""

    def _incident(self) -> Incident:
        result = PDFParser().parse_file(PDF_111045)
        assert result, "Parser returned empty list for 111045"
        return result[0]

    def test_returns_single_incident(self):
        assert len(PDFParser().parse_file(PDF_111045)) == 1

    def test_incident_id_set(self):
        import uuid
        uuid.UUID(self._incident().incident_id)

    def test_source_file_contains_111045(self):
        inc = self._incident()
        assert "111045" in (inc.metadata.source_file or "")

    def test_metadata_year_2026(self):
        assert self._incident().metadata.year == 2026

    def test_outcome_present(self):
        inc = self._incident()
        assert inc.outcome is not None


@pytest.mark.skipif(
    not all(p.exists() for p in _ALL_PDFS),
    reason="One or more test PDFs not found in data/inputs/pdf/",
)
class TestParsePDF111120:
    """Difficult intubation (CL IIb), Vascular/Orthopaedic, Emergency, Category D."""

    def _incident(self) -> Incident:
        result = PDFParser().parse_file(PDF_111120)
        assert result, "Parser returned empty list for 111120"
        return result[0]

    def test_returns_single_incident(self):
        assert len(PDFParser().parse_file(PDF_111120)) == 1

    def test_incident_id_set(self):
        import uuid
        uuid.UUID(self._incident().incident_id)

    def test_source_file_contains_111120(self):
        inc = self._incident()
        assert "111120" in (inc.metadata.source_file or "")

    def test_outcome_category_or_harm_severity_present(self):
        inc = self._incident()
        assert (
            inc.outcome.outcome_category is not None
            or inc.outcome.harm_severity is not None
        )


# ---------------------------------------------------------------------------
# Directory parsing
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not PDF_DIR.is_dir(),
    reason="data/inputs/pdf/ directory not found",
)
class TestParseDirectory:
    def test_returns_three_incidents(self):
        incidents = PDFParser().parse_directory(PDF_DIR)
        assert len(incidents) == 3

    def test_all_have_unique_ids(self):
        incidents = PDFParser().parse_directory(PDF_DIR)
        ids = [i.incident_id for i in incidents]
        assert len(ids) == len(set(ids))

    def test_all_have_source_file(self):
        for inc in PDFParser().parse_directory(PDF_DIR):
            assert inc.metadata.source_file is not None
            assert inc.metadata.source_file.endswith(".pdf")

    def test_all_have_outcome(self):
        for inc in PDFParser().parse_directory(PDF_DIR):
            assert inc.outcome is not None

    def test_all_have_patient(self):
        for inc in PDFParser().parse_directory(PDF_DIR):
            assert inc.patient is not None

    def test_all_have_surgery(self):
        for inc in PDFParser().parse_directory(PDF_DIR):
            assert inc.surgery is not None

    def test_all_have_metadata_year_2026(self):
        for inc in PDFParser().parse_directory(PDF_DIR):
            assert inc.metadata.year == 2026

    def test_all_have_metadata_month_april(self):
        for inc in PDFParser().parse_directory(PDF_DIR):
            assert inc.metadata.month == "April"

    def test_at_least_one_has_description(self):
        incidents = PDFParser().parse_directory(PDF_DIR)
        has_description = any(
            inc.incident.incident_description for inc in incidents
        )
        assert has_description, "None of the parsed incidents have a narrative description"

    def test_at_least_one_has_monitoring(self):
        incidents = PDFParser().parse_directory(PDF_DIR)
        has_monitoring = any(
            inc.anesthesia.monitoring for inc in incidents
        )
        assert has_monitoring, "None of the parsed incidents have monitoring data"


# ---------------------------------------------------------------------------
# fix_doubled_chars on real PDF content
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not PDF_110939.exists(),
    reason="Test PDF 110939 not found",
)
class TestFixDoubledCharsOnRealPDF:
    def _raw_text(self) -> str:
        import pdfplumber
        with pdfplumber.open(PDF_110939) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)

    def test_raw_text_not_empty(self):
        assert len(self._raw_text()) > 100

    def test_fixed_text_shorter_than_raw(self):
        raw = self._raw_text()
        fixed = fix_doubled_chars(raw)
        assert len(fixed) < len(raw), "fix_doubled_chars should reduce text length"

    def test_fixed_text_contains_readable_words(self):
        fixed = fix_doubled_chars(self._raw_text())
        # At least one of these common words should appear after fixing
        readable_words = ["the", "and", "or", "of", "in", "a", "is", "was"]
        found_any = any(f" {w} " in fixed.lower() for w in readable_words)
        assert found_any, "Fixed text does not contain common English words"


# ---------------------------------------------------------------------------
# Pipeline model validation — PDFIngestResult
# ---------------------------------------------------------------------------


class TestPDFIngestResultModel:
    def test_model_instantiates(self):
        from src.api.pipeline import PDFIngestResult
        result = PDFIngestResult(
            ingested=1,
            analyzed=1,
            failed_analysis=0,
            incident_ids=["id-001"],
            collection="incidents",
            dimension=1024,
            note="Analyzed PDF ingest — 1 incident(s) with AI metadata, 0 fell back to raw.",
        )
        assert result.ingested == 1
        assert result.analyzed == 1
        assert result.failed_analysis == 0

    def test_raw_ingest_note(self):
        from src.api.pipeline import PDFIngestResult
        result = PDFIngestResult(
            ingested=1,
            analyzed=0,
            failed_analysis=0,
            incident_ids=["id-001"],
            collection="incidents",
            dimension=1024,
            note="Raw PDF ingest — no ANTHROPIC_API_KEY; metadata will be empty.",
        )
        assert result.analyzed == 0
        assert "Raw" in result.note

    def test_partial_analysis(self):
        from src.api.pipeline import PDFIngestResult
        result = PDFIngestResult(
            ingested=3,
            analyzed=2,
            failed_analysis=1,
            incident_ids=["id-001", "id-002", "id-003"],
            collection="incidents",
            dimension=1024,
            note="2 analyzed, 1 failed.",
        )
        assert result.ingested == 3
        assert result.failed_analysis == 1
