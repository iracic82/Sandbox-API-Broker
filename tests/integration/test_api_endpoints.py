"""Integration tests for API endpoints."""

import pytest
from httpx import AsyncClient
from fastapi import status
from app.main import app
from app.core.config import settings
from unittest.mock import AsyncMock, patch


@pytest.fixture
def auth_headers():
    """Authentication headers for tests."""
    return {
        "Authorization": f"Bearer {settings.broker_api_token}",
        "X-Track-ID": "test-track-123"
    }


@pytest.fixture
def admin_auth_headers():
    """Admin authentication headers for tests."""
    return {
        "Authorization": f"Bearer {settings.broker_admin_token}"
    }


@pytest.mark.asyncio
async def test_health_check():
    """Test health check endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/healthz")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_readiness_check():
    """Test readiness check endpoint."""
    # Mock DynamoDB connection check
    with patch('app.api.metrics_routes.db_client') as mock_db:
        mock_db.table.table_status = "ACTIVE"

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/readyz")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] in ["ready", "degraded"]


@pytest.mark.asyncio
async def test_allocate_endpoint_requires_auth():
    """Test allocation endpoint requires authentication."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/v1/allocate")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_allocate_endpoint_requires_track_id():
    """Test allocation endpoint requires X-Track-ID header."""
    headers = {"Authorization": f"Bearer {settings.broker_api_token}"}

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/v1/allocate", headers=headers)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "X-Track-ID" in response.text


@pytest.mark.asyncio
async def test_allocate_endpoint_success(auth_headers):
    """Test successful sandbox allocation."""
    # Mock allocation service
    with patch('app.api.routes.allocation_service') as mock_service:
        from app.models.sandbox import Sandbox, SandboxStatus
        import time

        mock_sandbox = Sandbox(
            sandbox_id="test-sb-1",
            name="test-sandbox",
            external_id="ext-123",
            status=SandboxStatus.ALLOCATED,
            allocated_to_track="test-track-123",
            allocated_at=int(time.time()),
            lab_duration_hours=4,
        )
        mock_service.allocate = AsyncMock(return_value=mock_sandbox)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/v1/allocate", headers=auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sandbox_id"] == "test-sb-1"
        assert data["external_id"] == "ext-123"
        assert "expires_at" in data


@pytest.mark.asyncio
async def test_allocate_endpoint_pool_exhausted(auth_headers):
    """Test allocation fails when pool exhausted."""
    with patch('app.api.routes.allocation_service') as mock_service:
        mock_service.allocate = AsyncMock(side_effect=Exception("Pool exhausted"))

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/v1/allocate", headers=auth_headers)

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Pool exhausted" in response.text


@pytest.mark.asyncio
async def test_mark_for_deletion_success(auth_headers):
    """Test successful mark for deletion."""
    with patch('app.api.routes.allocation_service') as mock_service:
        from app.models.sandbox import Sandbox, SandboxStatus
        import time

        mock_sandbox = Sandbox(
            sandbox_id="test-sb-1",
            name="test-sandbox",
            external_id="ext-123",
            status=SandboxStatus.PENDING_DELETION,
            allocated_to_track="test-track-123",
            deletion_requested_at=int(time.time()),
        )
        mock_service.mark_for_deletion = AsyncMock(return_value=mock_sandbox)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/sandboxes/test-sb-1/mark-for-deletion",
                headers=auth_headers
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sandbox_id"] == "test-sb-1"
        assert data["status"] == "pending_deletion"


@pytest.mark.asyncio
async def test_mark_for_deletion_not_owner(auth_headers):
    """Test mark for deletion fails when not owner."""
    with patch('app.api.routes.allocation_service') as mock_service:
        mock_service.mark_for_deletion = AsyncMock(return_value=None)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/sandboxes/test-sb-1/mark-for-deletion",
                headers=auth_headers
            )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.asyncio
async def test_get_sandbox_success(auth_headers):
    """Test get sandbox by ID."""
    with patch('app.api.routes.allocation_service') as mock_service:
        from app.models.sandbox import Sandbox, SandboxStatus

        mock_sandbox = Sandbox(
            sandbox_id="test-sb-1",
            name="test-sandbox",
            external_id="ext-123",
            status=SandboxStatus.ALLOCATED,
            allocated_to_track="test-track-123",
        )
        mock_service.get_sandbox = AsyncMock(return_value=mock_sandbox)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/v1/sandboxes/test-sb-1",
                headers=auth_headers
            )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["sandbox_id"] == "test-sb-1"


@pytest.mark.asyncio
async def test_get_sandbox_not_found(auth_headers):
    """Test get sandbox returns 404 when not found."""
    with patch('app.api.routes.allocation_service') as mock_service:
        mock_service.get_sandbox = AsyncMock(return_value=None)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/v1/sandboxes/nonexistent",
                headers=auth_headers
            )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_admin_stats_requires_admin_auth(auth_headers):
    """Test admin stats requires admin token."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Try with regular token
        response = await client.get("/v1/admin/stats", headers=auth_headers)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_admin_stats_success(admin_auth_headers):
    """Test admin stats endpoint."""
    with patch('app.api.admin_routes.admin_service') as mock_service:
        mock_stats = {
            "total": 10,
            "available": 7,
            "allocated": 2,
            "pending_deletion": 1,
            "stale": 0,
            "deletion_failed": 0,
        }
        mock_service.get_stats = AsyncMock(return_value=mock_stats)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get("/v1/admin/stats", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 10
        assert data["available"] == 7


@pytest.mark.asyncio
async def test_admin_sync_success(admin_auth_headers):
    """Test admin sync endpoint."""
    with patch('app.api.admin_routes.admin_service') as mock_service:
        mock_result = {
            "status": "completed",
            "synced": 5,
            "marked_stale": 1,
            "duration_ms": 250,
        }
        mock_service.sync_from_csp = AsyncMock(return_value=mock_result)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/v1/admin/sync", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "completed"
        assert data["synced"] == 5


@pytest.mark.asyncio
async def test_admin_cleanup_success(admin_auth_headers):
    """Test admin cleanup endpoint."""
    with patch('app.api.admin_routes.admin_service') as mock_service:
        mock_result = {
            "status": "completed",
            "deleted": 3,
            "failed": 1,
            "duration_ms": 500,
        }
        mock_service.cleanup_pending_deletions = AsyncMock(return_value=mock_result)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/v1/admin/cleanup", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "completed"
        assert data["deleted"] == 3


@pytest.mark.asyncio
async def test_admin_auto_expire_success(admin_auth_headers):
    """Test admin auto-expire endpoint."""
    with patch('app.api.admin_routes.admin_service') as mock_service:
        mock_result = {
            "status": "completed",
            "expired": 2,
            "duration_ms": 300,
        }
        mock_service.auto_expire_allocations = AsyncMock(return_value=mock_result)

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post("/v1/admin/auto-expire", headers=admin_auth_headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "completed"
        assert data["expired"] == 2


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limiting middleware."""
    # This test would need actual rate limiter implementation
    # For now, verify the endpoint is accessible
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Make multiple rapid requests
        responses = []
        for _ in range(5):
            response = await client.get("/healthz")
            responses.append(response)

        # All should succeed (health check not rate limited)
        assert all(r.status_code == status.HTTP_200_OK for r in responses)


@pytest.mark.asyncio
async def test_cors_headers():
    """Test CORS headers are present."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.options("/healthz")

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers


@pytest.mark.asyncio
async def test_security_headers():
    """Test security headers are present."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/healthz")

        # Check for security headers
        headers = response.headers
        assert "x-content-type-options" in headers
        assert headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_swagger_docs_accessible():
    """Test Swagger documentation is accessible."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v1/docs")

    # Should redirect or return HTML
    assert response.status_code in [status.HTTP_200_OK, status.HTTP_307_TEMPORARY_REDIRECT]


@pytest.mark.asyncio
async def test_openapi_json_accessible():
    """Test OpenAPI JSON schema is accessible."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/v1/openapi.json")

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "openapi" in data
    assert "paths" in data
