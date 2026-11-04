import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from app.config import settings
from app.storage import store
from app.registry.agent_registry import registry
from app.main import app


@pytest.fixture(autouse=True)
def configure_isolated_environment(tmp_path: Path):
    """Ensure every test runs with an isolated temporary store and mock Gemini mode enabled.
    Guarantees zero mutation of real user data and zero external network calls."""
    original_data_file = settings.local_data_file
    original_store_path = store.path
    original_mock_mode = settings.gemini_mock_mode
    original_client = store.client

    # Force isolated test path and mock mode
    test_file = tmp_path / "agentsphere_isolated_test.json"
    test_file.write_text(json.dumps({}), encoding="utf-8")
    settings.gemini_mock_mode = True
    store.client = None
    store.path = test_file

    # Seed fresh default agents into the isolated test store
    registry.ensure_defaults()

    yield

    # Restore settings and store state
    settings.local_data_file = original_data_file
    settings.gemini_mock_mode = original_mock_mode
    store.path = original_store_path
    store.client = original_client


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app, raise_server_exceptions=True)
