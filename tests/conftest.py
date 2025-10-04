"""Pytest configuration and fixtures."""

import pytest
from app.core.config import settings


@pytest.fixture(scope="session")
def test_settings():
    """Test settings fixture."""
    settings.ddb_endpoint_url = "http://localhost:8000"
    settings.ddb_table_name = "SandboxPoolTest"
    settings.broker_api_token = "test_token"
    settings.broker_admin_token = "test_admin_token"
    return settings
