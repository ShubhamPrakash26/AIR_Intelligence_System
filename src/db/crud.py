from typing import List, Optional

from sqlmodel import select

from src.db.session import get_session, init_db
from src.db.models import IncidentRecord, AnalysisRecord


def _ensure_db() -> None:
    init_db()


def save_incident(parsed_incident: dict) -> IncidentRecord:
    _ensure_db()
    incident_id = parsed_incident.get("incident_id")
    if not incident_id:
        raise ValueError("parsed_incident must include 'incident_id'")

    with get_session() as session:
        existing = session.get(IncidentRecord, incident_id)
        if existing:
            return existing
        record = IncidentRecord(
            incident_id=incident_id,
            parsed_incident=parsed_incident,
            source_file=(parsed_incident.get("metadata") or {}).get("source_file"),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def save_analysis(analysis: dict) -> AnalysisRecord:
    _ensure_db()
    incident_id = analysis.get("incident_id")
    if not incident_id:
        raise ValueError("analysis must include 'incident_id'")

    with get_session() as session:
        record = AnalysisRecord(incident_id=incident_id, analysis=analysis, model_version=analysis.get("model_version"))
        session.add(record)
        session.commit()
        session.refresh(record)
        return record


def list_incidents() -> List[IncidentRecord]:
    _ensure_db()
    with get_session() as session:
        results = session.exec(select(IncidentRecord)).all()
        return results


def get_incident(incident_id: str) -> Optional[IncidentRecord]:
    _ensure_db()
    with get_session() as session:
        return session.get(IncidentRecord, incident_id)


def get_analyses_for_incident(incident_id: str) -> List[AnalysisRecord]:
    _ensure_db()
    with get_session() as session:
        stmt = select(AnalysisRecord).where(AnalysisRecord.incident_id == incident_id)
        return session.exec(stmt).all()
