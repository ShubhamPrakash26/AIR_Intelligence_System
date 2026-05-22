from fastapi.testclient import TestClient

from src.api.main import app
from src.db.crud import save_incident


client = TestClient(app)


def test_healthz_endpoint():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"


def test_ingest_excel_endpoint_all_files(excel_input_files):
    assert excel_input_files, "No Excel files found in data/inputs/excel or data/input/Excel"

    for sample_path in excel_input_files:
        with open(sample_path, "rb") as fh:
            files = {"file": (sample_path.name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            resp = client.post("/incidents/ingest/excel", files=files)

        assert resp.status_code == 200, f"{sample_path}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), f"{sample_path}: expected list response"
        assert len(data) > 0, f"{sample_path}: no incidents parsed"

        first = data[0]
        assert "incident_id" in first
        assert "patient" in first
        assert "surgery" in first
        assert "anesthesia" in first
        assert "metadata" in first


def test_analyze_excel_endpoint_all_files(excel_input_files):
    assert excel_input_files, "No Excel files found in data/inputs/excel or data/input/Excel"

    for sample_path in excel_input_files:
        with open(sample_path, "rb") as fh:
            files = {"file": (sample_path.name, fh, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            resp = client.post("/incidents/analyze/excel", files=files)

        assert resp.status_code == 200, f"{sample_path}: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), f"{sample_path}: expected list response"
        assert len(data) > 0, f"{sample_path}: no analyses returned"

        first = data[0]
        assert "incident_id" in first
        assert "incident_type" in first
        assert "severity" in first
        assert "severity_score" in first
        assert "root_cause" in first


def test_analyze_incidents_endpoint(sample_incident):
    payload = [sample_incident.model_dump(mode="json")]
    resp = client.post("/incidents/analyze", json=payload)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["count"] == 1
    assert len(data["analyses"]) == 1

    first = data["analyses"][0]
    assert first["incident_id"] == sample_incident.incident_id
    assert "incident_type" in first
    assert "severity" in first
    assert "root_cause" in first


def test_view_stored_incident_endpoint(sample_incident):
    payload = sample_incident.model_dump(mode="json")
    save_incident(payload)

    resp = client.get(f"/incidents/{sample_incident.incident_id}")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["incident"]["incident_id"] == sample_incident.incident_id
    assert isinstance(data["analyses"], list)


def test_view_stored_alias_endpoint(sample_incident):
    payload = sample_incident.model_dump(mode="json")
    save_incident(payload)

    resp = client.get("/incidents/stored")

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "incidents" in data


def test_ingest_pdf_endpoint_all_files(pdf_input_files):
    assert pdf_input_files, "No PDF files found in data/inputs/pdf or data/input/PDF"

    for sample_path in pdf_input_files:
        with open(sample_path, "rb") as fh:
            files = {"file": (sample_path.name, fh, "application/pdf")}
            resp = client.post("/incidents/ingest/pdf", files=files)

        assert resp.status_code == 200, f"{sample_path}: {resp.text}"
        payload = resp.json()
        assert payload.get("filename") == sample_path.name
        assert "message" in payload
