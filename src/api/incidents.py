from fastapi import APIRouter, UploadFile, File, HTTPException
from typing import List
from tempfile import NamedTemporaryFile
from pathlib import Path
import shutil

from src.ingestion.excel_parser import ExcelParser

router = APIRouter(prefix="/incidents", tags=["incidents"])


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
