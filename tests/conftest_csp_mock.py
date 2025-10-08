"""
CSP Mock Fixture - GUARANTEES NO REAL CSP API CALLS

This fixture patches ALL CSP service methods to prevent any real API calls during testing.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture(autouse=True)
def mock_csp_service():
    """
    Automatically mock CSP service for ALL tests.

    This fixture runs automatically (autouse=True) and ensures:
    1. NO real HTTP calls to csp.infoblox.com
    2. All CSP methods return mock data
    3. Safe to run tests without CSP credentials
    """

    # Mock CSP responses
    mock_sandboxes = [
        {
            "id": "test-sandbox-001",
            "name": "test-sandbox-001",
            "external_id": "uuid-001",
            "created_at": 1700000000,
        },
        {
            "id": "test-sandbox-002",
            "name": "test-sandbox-002",
            "external_id": "uuid-002",
            "created_at": 1700000001,
        },
    ]

    with patch('app.services.eng_csp.eng_csp_service') as mock_service:
        # Mock fetch_sandboxes - returns list of sandboxes
        mock_service.fetch_sandboxes = AsyncMock(return_value=mock_sandboxes)

        # Mock delete_sandbox - returns True (success)
        mock_service.delete_sandbox = AsyncMock(return_value=True)

        # Mock get_sandbox - returns single sandbox
        mock_service.get_sandbox = AsyncMock(return_value=mock_sandboxes[0])

        # Mock circuit breaker client (NO real HTTP)
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: mock_sandboxes
        ))
        mock_client.delete = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=lambda: {"success": True}
        ))
        mock_service.client = mock_client

        yield mock_service


@pytest.fixture(autouse=True)
def block_real_http_calls(monkeypatch):
    """
    Block ALL real HTTP calls as a safety net.

    If any code tries to make a real HTTP call, it will raise an error
    instead of hitting the real API.
    """
    import httpx

    async def raise_error(*args, **kwargs):
        raise RuntimeError(
            "❌ BLOCKED: Test tried to make a real HTTP call!\n"
            "All HTTP calls must be mocked. Check your test fixtures."
        )

    # Patch httpx to block real calls
    monkeypatch.setattr(httpx.AsyncClient, 'get', raise_error)
    monkeypatch.setattr(httpx.AsyncClient, 'post', raise_error)
    monkeypatch.setattr(httpx.AsyncClient, 'put', raise_error)
    monkeypatch.setattr(httpx.AsyncClient, 'delete', raise_error)
    monkeypatch.setattr(httpx.AsyncClient, 'patch', raise_error)


@pytest.fixture
def mock_dynamodb():
    """
    Mock DynamoDB client for tests that don't need a real DB.
    """
    with patch('app.db.dynamodb.db_client') as mock_db:
        mock_db.table = MagicMock()
        mock_db.table.scan = MagicMock(return_value={"Items": []})
        mock_db.table.query = MagicMock(return_value={"Items": []})
        mock_db.table.get_item = MagicMock(return_value={"Item": None})
        mock_db.table.put_item = MagicMock(return_value={})
        mock_db.table.delete_item = MagicMock(return_value={})
        yield mock_db
