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


# Import shared fixtures so pytest discovers them across modules
try:
    from tests.fixtures.sample_incidents import *  # noqa: F401,F403
except Exception:
    # If import fails, continue; tests that rely on fixtures will error explicitly
    pass
