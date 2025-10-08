# Production Fixes Summary

**Date**: 2025-10-08
**Version**: Pre-production hotfix
**Status**: Ready for testing

---

## **Critical Issues Fixed**

### **1. Rate Limiter Header Bug** ✅ FIXED
**File**: `app/middleware/rate_limit.py:93-97`

**Problem**:
- Rate limiter only checked `X-Track-ID` header
- Ignored the **preferred** `X-Instruqt-Sandbox-ID` header
- All clients using new header were rate-limited by IP (bypassing per-client limits)

**Fix**:
```python
# OLD - Only checked X-Track-ID
client_id = request.headers.get("X-Track-ID")

# NEW - Checks both headers
client_id = request.headers.get("X-Instruqt-Sandbox-ID")
if not client_id:
    client_id = request.headers.get("X-Track-ID")
if not client_id:
    client_id = request.client.host if request.client else "unknown"
```

---

###**2. CORS Missing Required Headers** ✅ FIXED
**File**: `app/main.py:104-118`

**Problem**:
- CORS middleware didn't allow `X-Instruqt-Sandbox-ID` header
- Browser blocked all requests using preferred header
- Missing `X-Instruqt-Track-ID` and `X-Sandbox-Name-Prefix`
- Missing `Retry-After` in exposed headers

**Fix**:
```python
# OLD
allow_headers=["Authorization", "Content-Type", "X-Track-ID", "Idempotency-Key"]
expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"]

# NEW
allow_headers=[
    "Authorization",
    "Content-Type",
    "X-Track-ID",  # Legacy
    "X-Instruqt-Sandbox-ID",  # Preferred
    "X-Instruqt-Track-ID",  # Optional track ID
    "X-Sandbox-Name-Prefix",  # Optional filter
    "Idempotency-Key",
]
expose_headers=[
    "X-Request-ID",
    "X-RateLimit-Limit",
    "X-RateLimit-Remaining",
    "Retry-After",  # For rate limit responses
]
```

---

### **3. CORS Wildcard Origins** ✅ FIXED
**File**: `app/main.py:98-101`, `app/core/config.py:56`

**Problem**:
- CORS allowed all origins (`*`)
- Security risk in production

**Fix**:
- Added `CORS_ALLOWED_ORIGINS` environment variable
- Defaults to `*` for development
- Production should set to specific origins: `CORS_ALLOWED_ORIGINS="https://app1.com,https://app2.com"`

---

### **4. Duplicate Background Jobs** ✅ FIXED
**Files**:
- `app/jobs/worker.py` (NEW)
- `app/main.py:172-188` (MODIFIED)
- `terraform/ecs_worker.tf` (NEW)

**Problem**:
- Running 2 ECS tasks for HA (correct)
- Both tasks ran background jobs (incorrect)
- Resulted in:
  - 2x CSP API calls (wasted resources)
  - Race conditions in cleanup job
  - Duplicate metrics

**Fix**:
- Created separate worker service (`app/jobs/worker.py`)
- Removed background jobs from API service
- Added Terraform config for worker ECS service (1 task only)
- Architecture:
  ```
  API Service: 2 tasks (HA for HTTP requests)
  Worker Service: 1 task (background jobs only)
  ```

---

### **5. /metrics Endpoint Performance** ✅ FIXED
**File**: `app/core/metrics.py:175-221`

**Problem**:
- `/metrics` endpoint scanned entire DynamoDB table on **every request**
- Prometheus scrapes every 15-30 seconds
- Expensive and unnecessary

**Fix**:
- Added 60-second cache for pool gauges
- Only scans DynamoDB once per minute
- Prometheus still gets updates, but not on every scrape

---

### **6. Hardcoded Index Names** ✅ FIXED
**File**: `app/services/admin.py:277, 292, 351, 361`

**Problem**:
- Used literal `"StatusIndex"` instead of `settings.ddb_gsi1_name`
- Could break if index name changed in config

**Fix**:
```python
# OLD
IndexName="StatusIndex"

# NEW
IndexName=settings.ddb_gsi1_name
```

---

## **Files Changed**

| File | Lines Changed | Type |
|------|---------------|------|
| `app/middleware/rate_limit.py` | +5 | Modified |
| `app/main.py` | +20, -12 | Modified |
| `app/core/config.py` | +3 | Modified |
| `app/core/metrics.py` | +25 | Modified |
| `app/services/admin.py` | +4 (x4 locations) | Modified |
| `app/jobs/worker.py` | +90 | **NEW** |
| `terraform/ecs_worker.tf` | +180 | **NEW** |
| `terraform/variables.tf` | +13 | Modified |

**Total**: 8 files, ~350 lines changed

---

## **Environment Variables Added**

```bash
# NEW: CORS configuration
CORS_ALLOWED_ORIGINS="*"  # For dev - set to specific origins in production
# Example for production:
# CORS_ALLOWED_ORIGINS="https://instruqt.com,https://app.example.com"
```

---

## **Terraform Changes**

### New Resources:
1. `aws_ecs_task_definition.worker` - Worker task definition
2. `aws_ecs_service.worker` - Worker ECS service (1 task)
3. `aws_cloudwatch_log_group.worker` - Worker logs
4. `aws_cloudwatch_metric_alarm.worker_cpu_high` - Worker CPU alarm
5. `aws_cloudwatch_metric_alarm.worker_memory_high` - Worker memory alarm

### New Variables:
- `worker_cpu` (default: 256)
- `worker_memory` (default: 512)

---

## **Backward Compatibility**

✅ **100% Backward Compatible**

- Legacy `X-Track-ID` header still works
- CORS still allows wildcard by default (configurable)
- All existing API endpoints unchanged
- Existing tests should pass

---

## **Testing Plan**

See `TESTING_PLAN.md` for detailed local testing steps.

**Summary**:
1. Mock CSP service (no real API calls)
2. Run existing 33 unit tests + 20 integration tests
3. Test new headers work correctly
4. Test worker service runs independently
5. Test metrics caching
6. Build Docker image
7. Deploy to production

---

## **Deployment Plan**

See `DEPLOYMENT_PLAN.md` for step-by-step deployment using AWS CLI with okta-sso.

**Summary**:
1. Build and push Docker image
2. Apply Terraform changes (adds worker service)
3. Deploy API service (removes background jobs)
4. Deploy worker service (runs background jobs)
5. Verify both services healthy
6. Monitor for 1 hour

---

## **Risk Assessment**

| Change | Risk | Mitigation |
|--------|------|------------|
| Rate limiter fix | LOW | Backward compatible, fixes bug |
| CORS headers | LOW | Backward compatible, adds headers |
| CORS origins | MEDIUM | Default unchanged, document for production |
| Worker service | MEDIUM | New service, well-tested pattern |
| Metrics caching | LOW | Improves performance, no API changes |
| Index names | LOW | Config-based, no runtime impact |

**Overall Risk**: 🟡 **MEDIUM** (mostly due to new worker service)

**Rollback Plan**:
- Worker service fails → Set `desired_count=0` for worker, re-enable jobs in API
- API issues → Rollback to previous task definition
- Full rollback time: ~5 minutes

---

## **Production Checklist**

Before deploying:
- [ ] Set `CORS_ALLOWED_ORIGINS` to specific origins (not `*`)
- [ ] Test locally with mocked CSP
- [ ] Run all tests
- [ ] Build Docker image
- [ ] Review Terraform plan
- [ ] Have rollback plan ready
- [ ] Monitor CloudWatch logs during deployment

---

**Status**: ✅ Code complete, ready for testing
