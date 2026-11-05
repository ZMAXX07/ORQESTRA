"""Pytest fixtures for backend test suite."""

import pytest
from fastapi.testclient import TestClient
from backend.app.core.config import Settings, get_settings
from backend.app.main import create_application


@pytest.fixture(scope="session")
def test_settings() -> Settings:
    """Fixture providing standardized test settings."""
    return Settings(
        ENVIRONMENT="test",
        DEBUG=False,
        APP_NAME="Orqestra API Test",
        CORS_ORIGINS=["http://testserver", "http://localhost:5173"],
        LOG_LEVEL="WARNING",
    )


@pytest.fixture(scope="function")
def client(test_settings: Settings) -> TestClient:
    """TestClient fixture overriding application settings for testing."""
    app = create_application(settings=test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
