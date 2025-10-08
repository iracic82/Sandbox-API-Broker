"""Test CORS now allows all required headers."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_cors_allows_instruqt_sandbox_id_header():
    """Test CORS allows X-Instruqt-Sandbox-ID header."""
    # Preflight request
    response = client.options(
        "/healthz",
        headers={
            "Origin": "https://instruqt.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Instruqt-Sandbox-ID",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-headers" in response.headers
    headers_lower = response.headers["access-control-allow-headers"].lower()
    assert "x-instruqt-sandbox-id" in headers_lower


def test_cors_allows_instruqt_track_id_header():
    """Test CORS allows X-Instruqt-Track-ID header."""
    response = client.options(
        "/healthz",
        headers={
            "Origin": "https://instruqt.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Instruqt-Track-ID",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-headers" in response.headers
    headers_lower = response.headers["access-control-allow-headers"].lower()
    assert "x-instruqt-track-id" in headers_lower


def test_cors_allows_sandbox_name_prefix_header():
    """Test CORS allows X-Sandbox-Name-Prefix header."""
    response = client.options(
        "/healthz",
        headers={
            "Origin": "https://instruqt.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Sandbox-Name-Prefix",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-headers" in response.headers
    headers_lower = response.headers["access-control-allow-headers"].lower()
    assert "x-sandbox-name-prefix" in headers_lower


def test_cors_exposes_retry_after_header():
    """Test CORS exposes Retry-After header."""
    response = client.options(
        "/healthz",
        headers={
            "Origin": "https://instruqt.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert "access-control-expose-headers" in response.headers
    headers_lower = response.headers["access-control-expose-headers"].lower()
    assert "retry-after" in headers_lower


def test_cors_still_allows_legacy_track_id():
    """Test CORS still allows legacy X-Track-ID header (backward compatibility)."""
    response = client.options(
        "/healthz",
        headers={
            "Origin": "https://instruqt.com",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Track-ID",
        },
    )

    assert response.status_code == 200
    assert "access-control-allow-headers" in response.headers
    headers_lower = response.headers["access-control-allow-headers"].lower()
    assert "x-track-id" in headers_lower
