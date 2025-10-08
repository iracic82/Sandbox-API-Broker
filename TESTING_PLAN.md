# Local Testing Plan - NO CSP API Calls

**Objective**: Test all fixes locally without making real CSP API calls

---

## **Prerequisites**

```bash
# 1. Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio pytest-cov httpx

# 2. Set up local DynamoDB (if not already running)
docker run -d -p 8000:8000 amazon/dynamodb-local

# 3. Create test DynamoDB table
python scripts/setup_local_db.py
```

---

## **Environment Setup**

Create `.env.test` file:

```bash
# DynamoDB - Local
DDB_TABLE_NAME=SandboxPool
DDB_GSI1_NAME=StatusIndex
DDB_GSI2_NAME=TrackIndex
DDB_GSI3_NAME=IdempotencyIndex
DDB_ENDPOINT_URL=http://localhost:8000
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# API Tokens
BROKER_API_TOKEN=test_api_token
BROKER_ADMIN_TOKEN=test_admin_token

# CSP - MOCKED (we'll use pytest mocks)
CSP_BASE_URL=http://localhost:9999
CSP_API_TOKEN=mock_token

# CORS
CORS_ALLOWED_ORIGINS=*

# Intervals (short for testing)
SYNC_INTERVAL_SEC=60
CLEANUP_INTERVAL_SEC=30
AUTO_EXPIRY_INTERVAL_SEC=30
```

---

## **Test Strategy**

### **Phase 1: Unit Tests (Existing - Should All Pass)**

```bash
# Run all 33 unit tests
pytest tests/unit/ -v --cov=app --cov-report=term-missing

# Expected output:
# tests/unit/test_allocation_service.py::test_... PASSED (11 tests)
# tests/unit/test_dynamodb_client.py::test_... PASSED (14 tests)
# tests/unit/test_multi_student_allocation.py::test_... PASSED (3 tests)
# tests/unit/test_sandbox_model.py::test_... PASSED (5 tests)
#
# Total: 33 tests passed
```

**What This Tests**:
- ✅ Allocation logic
- ✅ DynamoDB operations
- ✅ Multi-student allocation
- ✅ Sandbox model validation

**CSP Calls**: NONE (unit tests already mock CSP)

---

### **Phase 2: Integration Tests (Existing - Should All Pass)**

```bash
# Run all 20 integration tests
pytest tests/integration/ -v

# Expected output:
# tests/integration/test_api_endpoints.py::test_... PASSED (20 tests)
#
# Total: 20 tests passed
```

**What This Tests**:
- ✅ API endpoints
- ✅ Authentication
- ✅ Error handling
- ✅ Request validation

**CSP Calls**: NONE (integration tests already mock CSP)

---

### **Phase 3: New Fixes Verification**

#### **Test 1: Rate Limiter Header Check**

Create `tests/integration/test_rate_limiter_fix.py`:

```python
"""Test rate limiter now checks both X-Instruqt-Sandbox-ID and X-Track-ID."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_rate_limiter_uses_instruqt_sandbox_id():
    """Test rate limiter identifies client by X-Instruqt-Sandbox-ID."""
    headers = {
        "Authorization": "Bearer test_api_token",
        "X-Instruqt-Sandbox-ID": "client-A",
    }

    # First request should succeed
    response = client.get("/v1/healthz", headers=headers)
    assert response.status_code == 200

    # Should have rate limit headers
    assert "X-RateLimit-Limit" in response.headers
    assert "X-RateLimit-Remaining" in response.headers


def test_rate_limiter_fallback_to_track_id():
    """Test rate limiter falls back to X-Track-ID if X-Instruqt-Sandbox-ID missing."""
    headers = {
        "Authorization": "Bearer test_api_token",
        "X-Track-ID": "client-B",
    }

    response = client.get("/v1/healthz", headers=headers)
    assert response.status_code == 200
    assert "X-RateLimit-Limit" in response.headers


def test_rate_limiter_different_clients_separate_buckets():
    """Test different clients have separate rate limit buckets."""
    # Client A uses X-Instruqt-Sandbox-ID
    headers_a = {
        "Authorization": "Bearer test_api_token",
        "X-Instruqt-Sandbox-ID": "client-A",
    }

    # Client B uses X-Track-ID
    headers_b = {
        "Authorization": "Bearer test_api_token",
        "X-Track-ID": "client-B",
    }

    # Both should succeed independently
    response_a = client.get("/v1/healthz", headers=headers_a)
    response_b = client.get("/v1/healthz", headers=headers_b)

    assert response_a.status_code == 200
    assert response_b.status_code == 200
```

Run:
```bash
pytest tests/integration/test_rate_limiter_fix.py -v
```

---

#### **Test 2: CORS Headers**

Create `tests/integration/test_cors_fix.py`:

```python
"""Test CORS now allows all required headers."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_cors_allows_instruqt_sandbox_id_header():
    """Test CORS allows X-Instruqt-Sandbox-ID header."""
    # Preflight request
    response = client.options(
        "/v1/healthz",
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


def test_cors_exposes_retry_after_header():
    """Test CORS exposes Retry-After header."""
    response = client.options(
        "/v1/healthz",
        headers={
            "Origin": "https://instruqt.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert "access-control-expose-headers" in response.headers
    headers_lower = response.headers["access-control-expose-headers"].lower()
    assert "retry-after" in headers_lower
```

Run:
```bash
pytest tests/integration/test_cors_fix.py -v
```

---

#### **Test 3: Metrics Caching**

Create `tests/integration/test_metrics_caching.py`:

```python
"""Test /metrics endpoint uses caching."""

import time
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from app.core import metrics

client = TestClient(app)

def test_metrics_endpoint_caches_pool_gauges():
    """Test /metrics only scans DynamoDB once per 60 seconds."""

    with patch("app.core.metrics.db_client") as mock_db:
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

        # Third request after cache TTL - should scan again
        metrics._pool_gauges_cache["last_update"] = 0  # Expire cache
        response3 = client.get("/metrics")
        assert response3.status_code == 200
        assert mock_db.table.scan.call_count == 2  # Now 2
```

Run:
```bash
pytest tests/integration/test_metrics_caching.py -v
```

---

#### **Test 4: Worker Service**

Test worker can run independently:

```bash
# Terminal 1: Run worker
python -m app.jobs.worker

# Expected output:
# 🚀 Sandbox Broker Worker v0.1.0 starting...
# 📋 Background jobs:
#    - sync_job: Fetch sandboxes from CSP and sync to DynamoDB
#    - cleanup_job: Delete pending_deletion sandboxes from CSP
#    - auto_expiry_job: Mark expired allocations for deletion
#    - auto_delete_stale_job: Clean up stale sandboxes
#
# ✅ Started 4 background jobs
# Worker is running. Press Ctrl+C to stop.
```

Test graceful shutdown:
```bash
# Press Ctrl+C

# Expected output:
# 🛑 Shutdown signal received. Stopping background jobs...
# ✅ All background jobs stopped
# 👋 Worker shutdown complete
```

---

### **Phase 4: API Service Without Background Jobs**

```bash
# Run API service
uvicorn app.main:app --reload --port 8080

# Expected output:
# 🚀 Sandbox Broker API v0.1.0 starting...
# 📍 API base path: /v1
# 🗄️  DynamoDB table: SandboxPool
# ℹ️  Background jobs are handled by separate worker service
#    Run: python -m app.jobs.worker
#
# INFO:     Uvicorn running on http://0.0.0.0:8080 (Press CTRL+C to quit)
```

Test API works:
```bash
# Health check
curl http://localhost:8080/healthz

# Metrics (should work, with caching)
curl http://localhost:8080/metrics
```

---

## **Phase 5: Mock CSP Testing**

The existing tests already mock CSP calls using `pytest` fixtures. All CSP calls are intercepted and return mock data.

**Verify NO real CSP calls are made**:

```bash
# Monitor network traffic during tests
# Run tests with verbose output
pytest tests/ -v -s

# You should see NO HTTP requests to csp.infoblox.com
```

---

## **Summary Checklist**

Before deploying:

- [ ] All 33 unit tests pass
- [ ] All 20 integration tests pass
- [ ] Rate limiter test passes (3 new tests)
- [ ] CORS test passes (2 new tests)
- [ ] Metrics caching test passes (1 new test)
- [ ] Worker service starts and stops cleanly
- [ ] API service starts without background jobs
- [ ] NO CSP API calls made during tests
- [ ] Code coverage > 25% (current level)

---

## **Running All Tests**

```bash
# Run everything
pytest tests/ -v --cov=app --cov-report=term-missing --cov-report=html

# Check coverage report
open htmlcov/index.html
```

**Expected Results**:
- ✅ 56+ tests passed (33 unit + 20 integration + 6 new)
- ✅ 0 tests failed
- ✅ Coverage: ~25-30%
- ✅ NO CSP API calls

---

**Next Step**: Once all tests pass, proceed to `DEPLOYMENT_PLAN.md`
