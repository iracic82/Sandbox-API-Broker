"""Test /metrics endpoint uses caching."""

import time
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core import metrics

client = TestClient(app)


def test_metrics_endpoint_caches_pool_gauges():
    """Test /metrics only scans DynamoDB once per 60 seconds."""

    # Reset cache before test
    metrics._pool_gauges_cache["last_update"] = 0

    with patch("app.core.metrics.db_client") as mock_db:
        with patch("app.api.metrics_routes.db_client", mock_db):
            # Mock DynamoDB scan
            mock_db.table.scan.return_value = {"Items": []}

            # First request - should scan DB
            response1 = client.get("/metrics")
            assert response1.status_code == 200
            assert mock_db.table.scan.call_count == 1

            # Second request immediately after - should use cache
            response2 = client.get("/metrics")
            assert response2.status_code == 200
            assert mock_db.table.scan.call_count == 1  # Still 1, not 2!

            # Third request immediately after - still cached
            response3 = client.get("/metrics")
            assert response3.status_code == 200
            assert mock_db.table.scan.call_count == 1  # Still 1!

            # Expire cache manually
            metrics._pool_gauges_cache["last_update"] = 0

            # Fourth request after cache expiry - should scan again
            response4 = client.get("/metrics")
            assert response4.status_code == 200
            assert mock_db.table.scan.call_count == 2  # Now 2!


def test_metrics_endpoint_respects_cache_ttl():
    """Test metrics cache respects TTL setting."""

    # Reset cache and set short TTL for testing
    metrics._pool_gauges_cache["last_update"] = 0
    original_ttl = metrics._pool_gauges_cache["cache_ttl_seconds"]
    metrics._pool_gauges_cache["cache_ttl_seconds"] = 1  # 1 second TTL

    try:
        with patch("app.core.metrics.db_client") as mock_db:
            with patch("app.api.metrics_routes.db_client", mock_db):
                mock_db.table.scan.return_value = {"Items": []}

                # First request
                response1 = client.get("/metrics")
                assert response1.status_code == 200
                scan_count_1 = mock_db.table.scan.call_count

                # Wait for TTL to expire
                time.sleep(1.1)

                # Second request after TTL - should scan again
                response2 = client.get("/metrics")
                assert response2.status_code == 200
                scan_count_2 = mock_db.table.scan.call_count

                # Should have scanned twice
                assert scan_count_2 > scan_count_1

    finally:
        # Restore original TTL
        metrics._pool_gauges_cache["cache_ttl_seconds"] = original_ttl
        metrics._pool_gauges_cache["last_update"] = 0
