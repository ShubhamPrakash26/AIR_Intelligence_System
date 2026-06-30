"""PDF parser for AIR Anesthesia Incident Report (AIR Log) PDFs.

These are single-page form-fill documents from the Australian Patient Safety
Agency anesthesia incident reporting system.  Form field values are encoded
with doubled characters ("PPrriimmaarryy" → "Primary") — a pdfplumber extraction
artefact specific to this PDF format.  See fix_doubled_chars() for the
deduplication algorithm.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.models.incident import (
    AnesthesiaTechnique,
    ContextMetadata,
    Incident,
    IncidentDetails,
    OutcomeInfo,
    PatientInfo,
    SurgeryInfo,
)
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Outcome category letter → harm severity
_HARM_SEVERITY: dict[str, str] = {
    "A": "None",
    "B": "None",
    "C": "Low",
    "D": "Low",
    "E": "Moderate",
    "F": "High",
    "G": "Critical",
    "H": "Critical",
    "I": "Critical",
}


def fix_doubled_chars(text: str) -> str:
    """Correct the doubled-character encoding artefact in AIR Log PDF form fields.

    Every whitespace-delimited token is examined.  If its length is even and
    every adjacent pair (positions 0-1, 2-3, 4-5, …) consists of identical
    characters, the token is replaced with token[::2].

    This handles natural double letters correctly: "Balloon" doubled becomes
    "BBaalllloooonn" — the whole token is doubled — so it unfolds back to
    "Balloon".  An accidental "ll" in the middle of a word would not produce a
    fully-doubled token and is therefore left untouched.
    """
    def _fix_token(m: re.Match) -> str:
        t = m.group()
        n = len(t)
        if n < 2 or n % 2 != 0:
            return t
        if all(t[i] == t[i + 1] for i in range(0, n, 2)):
            return t[::2]
        return t

    return re.sub(r"\S+", _fix_token, text)


class PDFParser:
    """Parse AIR Anesthesia Incident Report PDFs into Incident objects.

    Usage::

        parser = PDFParser()
        incidents = parser.parse_file(Path("reports/110939.pdf"))
        # or
        all_incidents = parser.parse_directory(Path("data/inputs/pdf/"))
    """

    _SECTION_HEADERS: list[str] = [
        "Basic Information",
        "Procedure Information",
        "Incident Narrative Description",
        "Anesthesia Technique",
        "Monitoring Used",
        "Incident Demographics",
        "Equipment Related",
        "Airway Incident",
        "Patient Safety",
        "Medication Error",
        "Patient Outcome Category",
        "Reviewer",
    ]

    # ── Public API ─────────────────────────────────────────────────────────────

    def parse_file(self, path: Path) -> list[Incident]:
        """Parse a single PDF and return a list containing one Incident."""
        try:
            import pdfplumber
        except ImportError as exc:
            raise RuntimeError(
                "pdfplumber is required for PDF parsing. "
                "Install it with: poetry add pdfplumber"
            ) from exc

        path = Path(path)
        if path.suffix.lower() != ".pdf":
            raise ValueError(f"Expected a .pdf file, got: {path.suffix!r}")
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {path}")

        logger.info("PDFParser.parse_file: %s", path.name)

        try:
            with pdfplumber.open(path) as pdf:
                raw_text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages
                )
        except Exception as exc:
            raise RuntimeError(f"Failed to extract text from {path.name}: {exc}") from exc

        if not raw_text.strip():
            logger.warning("PDFParser: no text extracted from %s", path.name)
            return []

        fixed_text = fix_doubled_chars(raw_text)
        sections = self._parse_sections(fixed_text)
        incident = self._build_incident(sections, path.name, raw_text)
        logger.info("PDFParser: created incident %s from %s", incident.incident_id, path.name)
        return [incident]

    def parse_directory(self, directory: Path) -> list[Incident]:
        """Parse every PDF in *directory* and return all Incidents."""
        directory = Path(directory)
        if not directory.is_dir():
            raise NotADirectoryError(f"Not a directory: {directory}")

        pdf_files = sorted(directory.glob("*.pdf"))
        logger.info(
            "PDFParser.parse_directory: %d PDF(s) in %s", len(pdf_files), directory
        )

        incidents: list[Incident] = []
        for pdf_path in pdf_files:
            try:
                incidents.extend(self.parse_file(pdf_path))
            except Exception as exc:
                logger.warning("PDFParser: skipping %s — %s", pdf_path.name, exc)

        logger.info(
            "PDFParser: %d incident(s) parsed from %d PDF(s)",
            len(incidents),
            len(pdf_files),
        )
        return incidents

    # ── Section splitting ──────────────────────────────────────────────────────

    def _parse_sections(self, text: str) -> dict[str, str]:
        """Split fixed PDF text into named sections using header detection.

        Each known section header that appears at the start of a line becomes
        a key; its value is the text until the next header or end-of-string.
        The full text is always stored under the ``"full_text"`` key for
        fallback field extraction.
        """
        header_pattern = re.compile(
            r"^("
            + "|".join(re.escape(h) for h in self._SECTION_HEADERS)
            + r")[^\n]*$",
            re.IGNORECASE | re.MULTILINE,
        )

        matches = list(header_pattern.finditer(text))
        sections: dict[str, str] = {"full_text": text}

        if not matches:
            return sections

        for i, match in enumerate(matches):
            header_word = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            key = re.sub(r"['\s]+", "_", header_word.lower()).strip("_")
            sections[key] = content

        return sections

    # ── Incident construction ──────────────────────────────────────────────────

    def _build_incident(
        self, sections: dict[str, str], source_file: str, raw_text: str
    ) -> Incident:
        """Map extracted PDF sections to the Incident model."""
        full = sections.get("full_text", "")
        basic = sections.get("basic_information", full)
        procedure = sections.get("procedure_information", full)
        narrative = sections.get("incident_narrative_description", "")
        anesthesia_sec = sections.get("anesthesia_technique", full)
        monitoring_sec = sections.get("monitoring_used", full)
        demographics = sections.get("incident_demographics", full)
        outcome_sec = sections.get("patient_outcome_category", full)
        reviewer_sec = sections.get("reviewer", "")
        patient_safety_sec = sections.get("patient_safety", "")
        airway_sec = sections.get("airway_incident", "")
        equipment_sec = sections.get("equipment_related", "")

        # ── Patient ──────────────────────────────────────────────────────────
        patient = PatientInfo(
            age_range=self._field(basic, r"Age\s+Range[:\s]+([^\n]+)"),
            sex=self._field(basic, r"\bSex[:\s]+([^\n]+)"),
            weight_kg=self._float_field(basic, r"Weight[:\s]+([\d.]+)"),
            height_cm=self._float_field(basic, r"Height[:\s]+([\d.]+)"),
            bmi=self._float_field(basic, r"BMI[:\s]+([\d.]+)"),
            asa_grade=self._field(basic, r"ASA\s+Grade[:\s]+([^\n]+)"),
        )

        # ── Surgery ──────────────────────────────────────────────────────────
        surg_branch = self._field(
            procedure, r"Surgical\s+Branch[:\s]+([^\n]+)"
        ) or self._field(full, r"Surgical\s+Branch[:\s]+([^\n]+)")

        # Use line-anchored pattern so "Procedure:" doesn't grab "Type of Procedure:"
        surg_proc = self._field(
            procedure, r"(?:^|\n)Procedure[:\s]+([^\n]+)"
        ) or self._field(procedure, r"Surgical\s+Procedure[:\s]+([^\n]+)")

        type_of_proc = self._field(
            procedure, r"Type\s+of\s+Procedure[:\s]+([^\n]+)"
        ) or self._field(full, r"Type\s+of\s+Procedure[:\s]+([^\n]+)")

        surgery = SurgeryInfo(
            surgical_branch=surg_branch,
            procedure=surg_proc,
            type_of_procedure=type_of_proc,
        )

        # ── Incident details ──────────────────────────────────────────────────
        description = narrative.strip() or self._field(
            full,
            r"Incident\s+Narrative\s+Description[:\s]*\n([\s\S]+?)(?=\n[A-Z][a-z]|\Z)",
        )

        time_of = self._field(demographics, r"Time\s+of\s+Incident[:\s]+([^\n]+)")
        place_of = self._field(demographics, r"Place\s+of\s+Incident[:\s]+([^\n]+)")
        timing = self._field(
            demographics, r"Timing\s+of\s+(?:the\s+)?[Ee]vent[:\s]+([^\n]+)"
        )
        detection = self._field(demographics, r"Incident\s+Detection[:\s]+([^\n]+)")
        relation_raw = self._field(
            demographics, r"Incident\s+Relation[:\s]+([^\n]+)"
        )
        relation = (
            [r.strip() for r in re.split(r"[,;]", relation_raw) if r.strip()]
            if relation_raw
            else None
        )

        incident_types = self._incident_types(
            airway_sec, equipment_sec, patient_safety_sec
        )

        incident_details = IncidentDetails(
            incident_description=description or None,
            incident_type=incident_types or None,
            time_of_incident=time_of,
            place_of_incident=place_of,
            timing_of_event=timing,
            incident_detection=detection,
            incident_relation=relation,
        )

        # ── Anesthesia ────────────────────────────────────────────────────────
        anesthesia = AnesthesiaTechnique(
            primary_technique=self._primary_technique(anesthesia_sec),
            intubation_type=self._intubation_type(anesthesia_sec),
            monitoring=self._monitoring(monitoring_sec) or None,
        )

        # ── Outcome ───────────────────────────────────────────────────────────
        outcome_cat = self._outcome_category(outcome_sec)
        harm_severity = _HARM_SEVERITY.get(outcome_cat, None) if outcome_cat else None
        patient_safety_text = (
            self._field(outcome_sec, r"Patient\s+Safety[:\s]+([^\n]+)")
            or (patient_safety_sec.strip() or None)
        )

        outcome = OutcomeInfo(
            outcome_category=outcome_cat,
            harm_severity=harm_severity,
            patient_safety=patient_safety_text,
        )

        # ── Reviewer fields for raw_data ──────────────────────────────────────
        root_cause = self._reviewer_field(
            reviewer_sec,
            r"Root\s+Cause\s*(?:&|and)\s*Prevention[:\s]*(.*?)(?=Suggested|Review\s+#|\Z)",
        )
        key_learning = self._reviewer_field(
            reviewer_sec,
            r"Suggested\s+Course\s+of\s+Action[:\s]*(.*?)(?=Review\s+#|\Z)",
        )

        # ── Metadata ──────────────────────────────────────────────────────────
        now = datetime.now(timezone.utc)
        # Extract date from filename if available (e.g. AIRLog_20260419_110939)
        date_match = re.search(r"_(\d{8})_", source_file)
        if date_match:
            try:
                file_date = datetime.strptime(date_match.group(1), "%Y%m%d")
                month = file_date.strftime("%B")
                year = file_date.year
            except ValueError:
                month = now.strftime("%B")
                year = now.year
        else:
            month = now.strftime("%B")
            year = now.year

        metadata = ContextMetadata(
            source_file=source_file,
            upload_date=now,
            month=month,
            year=year,
        )

        return Incident(
            incident_id=str(uuid.uuid4()),
            patient=patient,
            surgery=surgery,
            incident=incident_details,
            anesthesia=anesthesia,
            outcome=outcome,
            metadata=metadata,
            raw_data={
                "source_file": source_file,
                "source_stem": Path(source_file).stem,
                "root_cause": root_cause,
                "key_learning": key_learning,
                "sections_found": [k for k in sections if k != "full_text"],
                "raw_text_length": len(raw_text),
            },
        )

    # ── Field extraction helpers ───────────────────────────────────────────────

    @staticmethod
    def _field(text: str, pattern: str) -> str | None:
        """Return first capture group from *pattern* against *text*, stripped."""
        if not text:
            return None
        m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if not m:
            return None
        val = m.group(1).strip()
        # Trim at next label-like line to avoid swallowing subsequent fields
        val = re.split(r"\n(?=[A-Z][a-zA-Z\s]+:)", val)[0].strip()
        return val if val else None

    @staticmethod
    def _float_field(text: str, pattern: str) -> float | None:
        """Return a float extracted by *pattern* or None."""
        if not text:
            return None
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        try:
            return float(m.group(1).replace(",", "."))
        except ValueError:
            return None

    @staticmethod
    def _outcome_category(text: str) -> str | None:
        """Extract the outcome category letter (A–I)."""
        if not text:
            return None
        m = re.search(r"\bCategory\s+([A-I])\d*\b", text, re.IGNORECASE)
        if m:
            return m.group(1).upper()
        m = re.search(r"^\s*([A-I])\s*[-–—]", text, re.MULTILINE)
        if m:
            return m.group(1).upper()
        return None

    @staticmethod
    def _primary_technique(text: str) -> str | None:
        """Extract the primary anaesthesia technique by keyword matching."""
        if not text:
            return None
        _TECHNIQUES = [
            "General Anesthesia",
            "General Anaesthesia",
            "Regional Anesthesia",
            "Regional Anaesthesia",
            "Combined Spinal Epidural",
            "Spinal",
            "Epidural",
            "Local Anesthesia",
            "Local Anaesthesia",
            "Monitored Anesthesia Care",
            "MAC",
            "Sedation",
        ]
        text_lower = text.lower()
        for tech in _TECHNIQUES:
            if tech.lower() in text_lower:
                return tech
        m = re.search(r"Primary[:\s]+([^\n]+)", text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _intubation_type(text: str) -> str | None:
        """Extract the airway device type."""
        if not text:
            return None
        tl = text.lower()
        if "i-gel" in tl:
            return "i-gel"
        if "lma" in tl or "laryngeal mask" in tl:
            return "LMA"
        if (
            "ett" in tl
            or "endotracheal" in tl
            or "intubat" in tl
        ):
            return "ETT"
        if "face mask" in tl or "mask anaes" in tl or "mask anes" in tl:
            return "Face Mask"
        return None

    @staticmethod
    def _monitoring(text: str) -> list[str]:
        """Return list of monitoring modalities present in *text*."""
        if not text:
            return []
        _MONITORS = [
            "ECG",
            "Pulse Oximeter",
            "Capnograph",
            "NIBP",
            "IBP",
            "Temperature",
            "BIS",
            "Nerve Stimulator",
            "TOF",
            "Arterial Line",
            "Central Venous",
            "PA Catheter",
            "Precordial Stethoscope",
            "Oesophageal Stethoscope",
        ]
        tl = text.lower()
        return [m for m in _MONITORS if m.lower() in tl]

    @staticmethod
    def _incident_types(
        airway_text: str, equipment_text: str, patient_safety_text: str
    ) -> list[str]:
        """Infer incident type labels from optional specialty sub-sections."""
        types: list[str] = []
        if airway_text and airway_text.strip():
            types.append("Airway Incident")
        if equipment_text and equipment_text.strip():
            types.append("Equipment Related")
        if patient_safety_text and patient_safety_text.strip():
            types.append("Patient Safety")
        return types

    @staticmethod
    def _reviewer_field(text: str, pattern: str) -> str | None:
        """Extract a narrative field from the reviewer's comments section."""
        if not text:
            return None
        m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not m:
            return None
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        return val if val else None
