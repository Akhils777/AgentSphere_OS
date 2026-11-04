"""Pytest configuration and fixtures for evaluation test suite.
Ensures isolated test storage and mock Gemini execution by default.
"""

import pytest
from app.config import settings
from app.storage import store


@pytest.fixture(autouse=True)
def ensure_evaluation_mock_mode():
    """Autouse fixture ensuring mock mode is strictly active for evaluation tests."""
    orig_mock = settings.gemini_mock_mode
    settings.gemini_mock_mode = True
    yield
    settings.gemini_mock_mode = orig_mock

