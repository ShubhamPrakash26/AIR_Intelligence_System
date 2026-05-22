from fastapi import APIRouter, UploadFile, File, HTTPException, Body
from typing import List
from tempfile import NamedTemporaryFile
from pathlib import Path
import shutil

from src.incident.understanding_agent import IncidentUnderstandingAgent
from src.ingestion.excel_parser import ExcelParser
from src.models.analysis import AIAnalysis, IncidentAnalysisBatchResponse
from src.models.incident import Incident
from src.utils.config import settings
from src.validation import ValidationAgent
import importlib

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _persist_incident_payload(parsed_incident: dict, analysis: AIAnalysis | None = None) -> None:
    if not settings.enable_persistence:
        return

    try:
        crud = importlib.import_module("src.db.crud")
        crud.save_incident(parsed_incident)
        if analysis is not None:
            crud.save_analysis(analysis.model_dump())
    except Exception:
        # Persistence must not block analysis responses.
        pass


def _analyze_incidents(incidents: list[Incident]) -> IncidentAnalysisBatchResponse:
    agent = IncidentUnderstandingAgent()
    validator = ValidationAgent()
    analyses = []
    for incident in incidents:
        analysis = agent.analyze_incident(incident).analysis
        analysis = validator.apply(incident, analysis)
        analyses.append(analysis)

        _persist_incident_payload(incident.model_dump(), analysis)

    return IncidentAnalysisBatchResponse(count=len(analyses), analyses=analyses)


@router.post("/ingest/excel")
async def ingest_excel(file: UploadFile = File(...)) -> List[dict]:
    """Ingest an Excel/CSV file and return parsed incidents as JSON."""
    # Save upload to a temporary file
    suffix = Path(file.filename).suffix or ".xlsx"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    parser = ExcelParser()
    try:
        incidents = parser.parse_file(tmp_path)
        for incident in incidents:
            _persist_incident_payload(incident.model_dump())
        # Convert Pydantic models to dicts
        return [inc.model_dump() for inc in incidents]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


@router.post("/analyze/excel")
async def analyze_excel(file: UploadFile = File(...)) -> List[dict]:
    """Ingest an Excel/CSV file and return AI analysis for each incident."""
    suffix = Path(file.filename).suffix or ".xlsx"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    parser = ExcelParser()
    try:
        incidents = parser.parse_file(tmp_path)
        batch = _analyze_incidents(incidents)
        return [analysis.model_dump() for analysis in batch.analyses]
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Uploaded file not found")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


@router.post("/analyze", response_model=IncidentAnalysisBatchResponse)
async def analyze_incidents(incidents: list[Incident] = Body(...)) -> IncidentAnalysisBatchResponse:
    """Analyze parsed incident objects and return the structured analysis batch."""
    try:
        return _analyze_incidents(incidents)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest/pdf")
async def ingest_pdf(file: UploadFile = File(...)) -> dict:
    """Placeholder PDF ingestion endpoint.

    Currently PDF extraction is not implemented. This endpoint saves the file and
    returns metadata and a message. Implement PDF parsing in `src.ingestion.pdf_parser`.
    """
    suffix = Path(file.filename).suffix or ".pdf"
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    # Placeholder response
    response = {
        "filename": file.filename,
        "saved_path": str(tmp_path),
        "message": "PDF parsing not implemented. File saved for later processing.",
    }

    return response


@router.get("/")
async def list_incidents():
    """List stored incidents when persistence is enabled."""
    if not settings.enable_persistence:
        return {"incidents": []}
    try:
        crud = importlib.import_module("src.db.crud")
        records = crud.list_incidents()
        return {"incidents": [r.model_dump() for r in records]}
    except Exception:
        return {"incidents": []}


@router.get("")
async def list_incidents_no_trailing_slash():
    """Alias for clients that call /incidents without the trailing slash."""
    return await list_incidents()


@router.get("/stored")
async def list_stored_incidents():
    """Explicit alias for viewing stored incidents in the platform."""
    return await list_incidents()


@router.get("/stored/")
async def list_stored_incidents_no_trailing_slash():
    """Alias for clients that call /incidents/stored with or without a trailing slash."""
    return await list_stored_incidents()


@router.get("/{incident_id}")
async def get_incident(incident_id: str):
    """Return a stored incident and its analyses when persistence is enabled."""
    if not settings.enable_persistence:
        raise HTTPException(status_code=404, detail="Persistence is disabled")
    try:
        crud = importlib.import_module("src.db.crud")
        inc = crud.get_incident(incident_id)
        analyses = crud.get_analyses_for_incident(incident_id)
        if not inc:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"incident": inc.model_dump(), "analyses": [a.model_dump() for a in analyses]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
