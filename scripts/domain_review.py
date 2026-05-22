"""Generate a small domain-review report by running the IncidentUnderstandingAgent.

Usage:
    python scripts/domain_review.py [path/to/excel.xlsx]

If no file is provided the script runs the agent over a built-in sample incident.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import List

from src.incident.understanding_agent import IncidentUnderstandingAgent
from src.ingestion.excel_parser import ExcelParser
from src.models.incident import Incident, PatientInfo, SurgeryInfo, IncidentDetails, AnesthesiaTechnique, OutcomeInfo, ContextMetadata
from src.utils.helpers import generate_incident_id


def make_sample_incident() -> Incident:
    return Incident(
        incident_id=generate_incident_id(),
        patient=PatientInfo(age_range="21-30 years", sex="Female"),
        surgery=SurgeryInfo(type_of_procedure="Elective", surgical_branch="Gynecology", procedure="DHC"),
        incident=IncidentDetails(incident_description="Insufflator malfunction during laparoscopy", incident_details="Device failed on insufflation"),
        anesthesia=AnesthesiaTechnique(primary_technique="General Anesthesia", monitoring=["ECG", "Capnograph"]),
        medication_error=None,
        outcome=OutcomeInfo(outcome_category="E", patient_safety="Anesthetic delivered - surgery not done", harm_severity="High"),
        metadata=ContextMetadata(source_file="domain_review_sample", upload_date=datetime.now(), month="May", year=2026),
    )


def analyze_from_excel(path: Path) -> List[Incident]:
    parser = ExcelParser()
    return parser.parse_file(path)


def render_report(analyses: List[dict]) -> str:
    lines: List[str] = []
    lines.append("# Domain Review Report")
    lines.append(f"Generated: {datetime.now().isoformat()}")
    lines.append("")

    for a in analyses:
        lines.append(f"## Incident {a['incident_id']}")
        lines.append(f"- Severity: {a.get('severity')} ({a.get('severity_score')})")
        lines.append(f"- Types: {', '.join(a.get('incident_type', []))}")
        lines.append(f"- Root cause: {a.get('root_cause')}")
        lines.append(f"- Key learning: {a.get('key_learning')}")
        lines.append("")

    return "\n".join(lines)


def main(argv: List[str]) -> int:
    agent = IncidentUnderstandingAgent()

    if len(argv) > 1:
        p = Path(argv[1])
        if not p.exists():
            print(f"File not found: {p}")
            return 2
        incidents = analyze_from_excel(p)
    else:
        incidents = [make_sample_incident()]

    analyses = [agent.analyze_incident(i).analysis.model_dump() for i in incidents]

    report = render_report(analyses)
    out = Path("domain_review.md")
    out.write_text(report, encoding="utf-8")
    print(f"Wrote {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
