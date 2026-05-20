import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_ingest_excel_endpoint():
    sample_path = Path("data/input/Log.xlsx")
    assert sample_path.exists(), f"Sample file not found: {sample_path}"

    with open(sample_path, "rb") as fh:
        files = {"file": (sample_path.name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        resp = client.post("/incidents/ingest/excel", files=files)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Basic structure checks
    first = data[0]
    assert "incident_id" in first
    assert "patient" in first
    assert "surgery" in first
    assert "anesthesia" in first
    assert "metadata" in first
