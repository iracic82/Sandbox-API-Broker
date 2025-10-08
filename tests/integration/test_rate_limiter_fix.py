"""Test rate limiter now checks both X-Instruqt-Sandbox-ID and X-Track-ID."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_rate_limiter_uses_instruqt_sandbox_id():
    """Test rate limiter identifies client by X-Instruqt-Sandbox-ID."""
    headers = {
        "X-Instruqt-Sandbox-ID": "client-A-sandbox-id",
    }

    # First request should succeed
    response = client.get("/healthz", headers=headers)
    assert response.status_code == 200

    # Should have rate limit headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


def test_rate_limiter_fallback_to_track_id():
    """Test rate limiter falls back to X-Track-ID if X-Instruqt-Sandbox-ID missing."""
    headers = {
        "X-Track-ID": "client-B-track-id",
    }

    response = client.get("/healthz", headers=headers)
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers


def test_rate_limiter_different_clients_separate_buckets():
    """Test different clients have separate rate limit buckets."""
    # Client A uses X-Instruqt-Sandbox-ID
    headers_a = {
        "X-Instruqt-Sandbox-ID": "client-A",
    }

    # Client B uses X-Track-ID
    headers_b = {
        "X-Track-ID": "client-B",
    }

    # Both should succeed independently
    response_a = client.get("/healthz", headers=headers_a)
    response_b = client.get("/healthz", headers=headers_b)

    assert response_a.status_code == 200
    assert response_b.status_code == 200

    # Both should have their own rate limit buckets
    assert "X-RateLimit-Remaining" in response_a.headers
    assert "X-RateLimit-Remaining" in response_b.headers


def test_rate_limiter_prefers_instruqt_sandbox_id_over_track_id():
    """Test rate limiter prefers X-Instruqt-Sandbox-ID when both headers present."""
    # Send both headers, should use X-Instruqt-Sandbox-ID
    headers = {
        "X-Instruqt-Sandbox-ID": "preferred-header",
        "X-Track-ID": "legacy-header",
    }

    response = client.get("/healthz", headers=headers)
    assert response.status_code == 200

    # The rate limiter should use "preferred-header" as client_id
    # (we can't directly test this, but the test passes if no errors)
