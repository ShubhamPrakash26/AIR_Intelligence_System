import os
from src.utils.config import Settings


def test_settings_defaults():
    s = Settings()
    assert s.app_name.startswith("AIR Clinical")
    assert s.api_port == 8000
    assert s.data_dir.name == "data"


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("API_PORT", "9000")
    # Create a fresh Settings instance to pick up env var
    s = Settings()
    assert s.api_port == 9000

