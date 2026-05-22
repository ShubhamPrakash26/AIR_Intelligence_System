"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import pytest


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Get path to test data directory."""
    return project_root / "tests" / "fixtures"


@pytest.fixture(scope="session")
def temp_data_dir(tmp_path_factory):
    """Create temporary data directory for tests."""
    return tmp_path_factory.mktemp("test_data")


def _discover_input_files(preferred: Path, fallback: Path, pattern: str) -> list[Path]:
    """Resolve input files from preferred path, with legacy fallback."""
    search_dir = preferred if preferred.exists() else fallback
    if not search_dir.exists():
        return []
    return sorted(search_dir.glob(pattern))


@pytest.fixture(scope="session")
def excel_input_files() -> list[Path]:
    """All Excel files used for ingestion tests.

    Preferred: data/inputs/excel
    Fallback: data/input/Excel
    """
    preferred = project_root / "data" / "inputs" / "excel"
    fallback = project_root / "data" / "input" / "Excel"
    return _discover_input_files(preferred, fallback, "*.xlsx")


@pytest.fixture(scope="session")
def pdf_input_files() -> list[Path]:
    """All PDF files used for ingestion tests.

    Preferred: data/inputs/pdf
    Fallback: data/input/PDF
    """
    preferred = project_root / "data" / "inputs" / "pdf"
    fallback = project_root / "data" / "input" / "PDF"
    return _discover_input_files(preferred, fallback, "*.pdf")


# Import shared fixtures so pytest discovers them across modules
try:
    from tests.fixtures.sample_incidents import *  # noqa: F401,F403
except Exception:
    # If import fails, continue; tests that rely on fixtures will error explicitly
    pass
