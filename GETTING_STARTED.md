# Getting Started — AIR Clinical Incident Intelligence Engine

This guide helps developers set up a local development environment, run tests, and start working on the AIR Clinical Incident Intelligence Engine.

Prerequisites
- OS: Windows / macOS / Linux
- Python 3.11+
- Poetry (recommended) — https://python-poetry.org/
- Git

Environment-specific notes
- Windows (PowerShell): use the integrated PowerShell terminal. If using Windows Subsystem for Linux (WSL), prefer the WSL shell for POSIX compatibility.
- macOS / Linux: use your system shell (bash/zsh). Ensure Python 3.11 is the active interpreter.

Quick setup (recommended)
1. Clone the repository (if not already):

```powershell
git clone <repo_url> AIR_Intelligence_System
cd AIR_Intelligence_System
```

2. Install dependencies with Poetry:

Windows PowerShell

```powershell
poetry install
```

WSL / macOS / Linux

```bash
poetry install
```

3. Activate the virtual environment (optional but convenient):

PowerShell

```powershell
poetry shell
```

WSL / macOS / Linux

```bash
poetry shell
```

4. Copy environment template and set required variables:

```powershell
copy .env.example .env
# Edit .env to set API keys and any local overrides
```

Core commands
- Run tests:

```powershell
poetry run pytest
```

- Run linter (ruff):

```powershell
poetry run ruff check src tests
```

- Format code (black):

```powershell
poetry run black src tests
```

- Start FastAPI dev server (once implemented):

PowerShell

```powershell
poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

WSL / macOS / Linux

```bash
poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Project layout (high level)
- `src/` — application source code
  - `models/` — Pydantic models for incidents and AI outputs
  - `ingestion/` — parsers and ingestion code (`excel_parser.py`)
  - `normalization/` — normalization engine (Week 2)
  - `utils/` — helpers, config, and logger
  - `agents/`, `embeddings/`, `vector_store/`, `retrieval/`, `insights/` — phased components
- `tests/` — unit and integration tests
  - `fixtures/` — shared test fixtures
  - `unit/` — unit tests
- `pyproject.toml` — Poetry dependencies and tooling
- `.env` / `.env.example` — environment configuration

Configuration
- Environment variables are loaded via Pydantic Settings. Required values:
  - `ANTHROPIC_API_KEY` — (for Phase 2+ LLM integration)
  - `QDRANT_URL`, `QDRANT_API_KEY` — (for Phase 3 vector store)
- Use `.env.example` as the template and **never** commit secrets.

Testing notes
- Tests are run with `pytest` and configured in `pyproject.toml`.
- Coverage report is generated automatically when tests run with the configured `--cov` options.
- Example:

```powershell
poetry run pytest --maxfail=1 --disable-warnings -q
```

Developer workflow
1. Create a feature branch: `git checkout -b feat/your-feature`
2. Run tests locally and ensure linting passes
3. Commit small, focused changes with clear messages
4. Open a Pull Request and request reviews

Notes and tips
- Models use Pydantic v2 with `model_config = ConfigDict(...)` patterns.
- Use the fixtures in `tests/fixtures/sample_incidents.py` for realistic test data.
- `src/ingestion/excel_parser.py` supports `.xlsx`, `.xls`, and `.csv` sources and is the primary entry point for batch ingestion in Phase 1.
- The `Plan.md`, `Tasks.md`, and `project_overview.md` files contain the roadmap, task tracking, and architecture respectively — consult them before large changes.

Troubleshooting
- If tests fail due to missing environment variables, copy `.env.example` to `.env` and set required values.
- If pytest cannot discover fixtures, ensure `conftest.py` and `tests/fixtures/__init__.py` exist and `src` is on `sys.path` (this repo sets it in `conftest.py`).

Contact
- For project questions, see `project_overview.md` or reach out to the AIR Team.

Last updated: May 20, 2026

API Endpoints & Testing

The project exposes API endpoints under `/incidents` for ingestion. Below are examples and expected responses.

1) Excel ingestion

- Endpoint: `POST /incidents/ingest/excel`
- Accepts: multipart form upload, field `file` (Excel `.xlsx`/`.xls` or `.csv`)
- Example (PowerShell):

```powershell
curl -X POST "http://localhost:8000/incidents/ingest/excel" -F "file=@C:\path\to\incidents.xlsx"
```

- Example (bash):

```bash
curl -X POST "http://localhost:8000/incidents/ingest/excel" -F "file=@/path/to/incidents.xlsx"
```

- Response: `200 OK` with JSON array of parsed incidents. Each incident object matches the `Incident` model and includes fields like `incident_id`, `patient`, `surgery`, `incident`, `anesthesia`, `outcome`, `metadata`, `raw_data`.

Sample response (truncated):

```json
[
  {
    "incident_id": "550e8400-e29b-...",
    "patient": {"age_range": "21-30 years", "sex": "Female", ...},
    "surgery": {"type_of_procedure": "Elective", ...},
    "incident": {"incident_description": "Insufflator malfunction", ...},
    "anesthesia": {"primary_technique": "General Anesthesia", ...},
    "outcome": {"outcome_category": "E", ...},
    "metadata": {"source_file": "incidents.xlsx"},
    "raw_data": {"Incident Narrative Description": "Insufflator malfunction", ...}
  }
]
```

Notes:
- If parsing a CSV, the endpoint accepts `.csv` files.
- On malformed files you may get `400` with an error message or `500` for internal errors.

2) PDF ingestion (placeholder)

- Endpoint: `POST /incidents/ingest/pdf`
- Accepts: multipart form upload, field `file` (PDF)
- Response: `200 OK` with metadata and message indicating parsing is not yet implemented. Example:

```json
{
  "filename": "report.pdf",
  "saved_path": "/tmp/tmpabcd1234.pdf",
  "message": "PDF parsing not implemented. File saved for later processing."
}
```

3) Health check

- Endpoint: `GET /healthz` — returns `{ "status": "ok" }`

Testing strategy for major endpoints (Excel/PDF)

- Unit tests: Mock `UploadFile` to call the endpoint directly with a small in-memory Excel/CSV and assert on returned JSON shape.
- Integration tests: Run the app locally and use `curl` or `requests` to upload representative files.

Recommended test cases for Excel ingestion:
- Valid small Excel with 1 row: expect a single-element list with fully populated `Incident` fields.
- CSV format with same columns: ensure CSVs are parsed correctly.
- File missing required columns: endpoint should return `200` but the parser's `validate_schema` will flag missing columns — consider asserting on `raw_data` or metadata.
- Rows with missing values: verify parser handles NaN/empty strings and returns `null` for missing fields.

Recommended test cases for PDF ingestion:
- Upload a small PDF: expect `200` and message indicating placeholder status.
- (Future) Once PDF parser implemented: test that parsed text or extracted structured fields are returned.

Running these tests locally

- Start the server:

PowerShell

```powershell
poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

WSL / macOS / Linux

```bash
poetry run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

- Then use `curl` examples above or the included `tests/` fixtures for automated checks.

Docker (local development)

- Build image:

```bash
docker build -t air-intel:dev .
```

- Run container (ports forwarded):

```bash
docker run --rm -p 8000:8000 -v "${PWD}:/app" air-intel:dev
```

