# Sandbox Broker API - AWS Implementation Summary

## Project Overview
Building a high-concurrency Sandbox Broker API using AWS services (DynamoDB + ECS/Fargate) to allocate pre-created CSP sandboxes to Instruqt tracks at scale (1000+ concurrent requests).

## Project Status

**Current Status**: 🚀 **PRODUCTION LIVE**

**Production URL**: `https://api-sandbox-broker.highvelocitynetworking.com/v1`

**Completed Phases**:
- ✅ **Phase 1**: Core FastAPI + DynamoDB (allocation, deletion, idempotency)
- ✅ **Phase 2**: Admin Endpoints + Structured Logging
- ✅ **Phase 3**: Observability & Background Jobs (Prometheus metrics, health checks)
- ✅ **Phase 4**: Enhanced Security & Resilience (rate limiting, security headers, circuit breaker)
- ✅ **Phase 5**: ENG CSP Production Integration (real API calls, error handling)
- ✅ **Phase 6**: AWS Production Deployment (49/49 resources, HTTPS, multi-AZ, auto-scaling)
- ✅ **Phase 7**: Testing & Load Testing (33/33 unit tests, 18/20 integration tests, multi-student load test with ZERO double-allocations)

**Next Phase**: Phase 8 - CI/CD & Deployment Pipeline

## Architecture Stack
- **API Framework**: FastAPI (async)
- **Database**: DynamoDB with GSIs
- **Compute**: ECS Fargate (stateless, multi-AZ)
- **Load Balancer**: ALB with HTTPS
- **Sync Job**: EventBridge Scheduler → ECS Task/Lambda
- **Observability**: CloudWatch + Prometheus metrics
- **Security**: Secrets Manager (Phase 1) → Cognito (Phase 2)

## Core Requirements
- Zero double-allocations via atomic DynamoDB conditional writes
- Idempotency support via X-Track-ID header
- <300ms claim latency (99th percentile)
- Graceful handling of pool exhaustion and sync failures
- Periodic sync from ENG tenant (10-minute intervals)

## DynamoDB Schema
**Table**: `SandboxPool`
- **PK**: `SBX#{sandbox_id}`, **SK**: `META`
- **Attributes**:
  - `sandbox_id` (STRING) - Unique UUID
  - `name` (STRING) - Human-readable name
  - `external_id` (STRING) - ENG CSP identifier
  - `status` (STRING) - available | allocated | pending_deletion | stale | deletion_failed
  - `allocated_to_track` (STRING) - Track ID (NULL if available)
  - `allocated_at` (NUMBER) - Unix timestamp
  - `lab_duration_hours` (NUMBER) - Default 4
  - `deletion_requested_at` (NUMBER) - Unix timestamp
  - `deletion_retry_count` (NUMBER) - Retry attempts for failed deletions
  - `last_synced` (NUMBER) - Unix timestamp from ENG sync
  - `idempotency_key` (STRING) - X-Track-ID for deduplication
  - `created_at` (NUMBER) - Unix timestamp
  - `updated_at` (NUMBER) - Unix timestamp

- **GSI1**: `StatusIndex`
  - PK: `status`, SK: `allocated_at` (for FIFO allocation and expiry queries)

- **GSI2**: `TrackIndex`
  - PK: `allocated_to_track`, SK: `allocated_at` (for track lookup)

- **GSI3**: `IdempotencyIndex` (optional, for faster idempotency checks)
  - PK: `idempotency_key`, SK: `allocated_at`

## Sandbox Lifecycle Model

### Happy Path (Student Stops Lab Early)
1. **Available** → Sandbox in pool, ready for allocation
2. **Allocated** → Instruqt track claims sandbox for lab (up to 4-hour max)
3. **Student Stops Lab** → Track immediately calls `POST /mark-for-deletion/{sandbox_id}`
4. **Pending Deletion** → Sandbox flagged instantly, removed from allocation pool
5. **Cleanup Job** → Processes pending_deletion items every ~5 min, deletes from ENG CSP
6. **Total cleanup time**: ~5 minutes from student stop

### Safety Net (Orphaned Allocations)
1. **Allocated** → Track claims sandbox but crashes/fails to call mark-for-deletion
2. **Auto-Expiry Job** → After 4 hours + 30min grace period, auto-marks as pending_deletion
3. **Cleanup Job** → Deletes from ENG CSP
4. **Purpose**: Prevents resource leaks if track fails

### Key Design Principles
- **Immediate deletion on stop** - Track can call mark-for-deletion anytime after allocation
- **No waiting** - Don't hold sandbox for full 4h if student finishes early
- **4-hour timer is safety timeout** - Not a required wait period
- **One-time use** - Sandboxes never return to pool
- **Defensive validation** - Prevent deletion marking after 4h window (ownership expired)
- **Cost efficiency** - Faster cleanup = lower CSP costs

## API Endpoints

### Public Endpoints (Track Access)
- `POST /v1/allocate` - Atomically allocate available sandbox to track
  - Headers: `Authorization: Bearer <token>`, `X-Track-ID: <track_id>`, `Idempotency-Key: <optional>`
  - Response: `{ sandbox_id, name, external_id, allocated_at, expires_at }`
  - Status: 201 (created), 200 (idempotent), 409 (no sandboxes), 429 (rate limit)

- `POST /v1/sandboxes/{sandbox_id}/mark-for-deletion` - Flag sandbox for deletion
  - Headers: `Authorization: Bearer <token>`, `X-Track-ID: <track_id>`
  - Response: `{ sandbox_id, status: "pending_deletion", deletion_requested_at }`
  - Status: 200 (success), 403 (not owner/expired), 404 (not found)

- `GET /v1/sandboxes/{sandbox_id}` - Get sandbox details (for allocated track only)
  - Headers: `Authorization: Bearer <token>`, `X-Track-ID: <track_id>`
  - Response: `{ sandbox_id, name, external_id, status, allocated_at, expires_at }`

### Admin Endpoints (Internal/Ops)
- `GET /v1/admin/sandboxes` - List sandboxes (paginated, filterable by status)
  - Query: `?status=available&limit=50&cursor=<token>`
  - Requires admin token

- `POST /v1/admin/sync` - Trigger ENG tenant sync
  - Requires admin token

- `POST /v1/admin/cleanup` - Process pending_deletion sandboxes
  - Requires admin token

### Observability Endpoints
- `GET /metrics` - Prometheus metrics (no auth)
- `GET /healthz` - Health check (no auth)
- `GET /readyz` - Readiness check (no auth)

## Concurrency Strategy
1. **Idempotency-first**: Reuse active allocation by X-Track-ID (if within 4-hour window)
2. **Candidate fan-out**: Read K=10-20 from GSI1 (status='available'), shuffle to avoid thundering herd
3. **Atomic allocation**: UpdateItem with ConditionExpression checking status='available'
4. **Retry logic**: ConditionalCheckFailed with jitter, return 409 when exhausted
5. **Partition health**: UUID sandbox_ids for entropy

## Sandbox Allocation Lifecycle Details

### Timing & Windows
- **Max Lab Duration**: 4 hours (configurable via LAB_DURATION_HOURS)
- **Grace Period**: 30 minutes after 4h for auto-expiry
- **Cleanup Frequency**: Every 5 minutes (CLEANUP_INTERVAL_SEC=300)
- **Deletion Latency**: ~5 minutes from mark-for-deletion call to ENG CSP deletion

### Status Flow
1. **`available`** → Ready for allocation (initial state from ENG sync)
2. **`allocated`** → In use by track (locked, not allocatable)
3. **`pending_deletion`** → Flagged for cleanup (immediate on student stop OR auto after 4.5h)
4. **`stale`** → Missing from ENG sync (not allocatable, needs investigation)

### Mark-for-Deletion Logic
```
IF sandbox.allocated_to_track == requesting_track_id:
    IF allocated_at + 4h > now:
        # Normal case: student stopped early
        SET status = 'pending_deletion'
        SET deletion_requested_at = now
        RETURN 200 OK
    ELSE:
        # Ownership expired, shouldn't happen if track behaves
        RETURN 403 Forbidden (allocation expired)
ELSE:
    # Wrong track trying to delete
    RETURN 403 Forbidden (not owner)
```

### Auto-Expiry Job Logic
```
Find all sandboxes WHERE:
    status = 'allocated'
    AND allocated_at + 4.5h < now

FOR EACH orphaned_sandbox:
    SET status = 'pending_deletion'
    SET deletion_requested_at = now
    LOG warning (track failed to cleanup)
```

### Cleanup Job Logic
```
Find all sandboxes WHERE:
    status = 'pending_deletion'

FOR EACH sandbox:
    TRY:
        Call ENG CSP DELETE /api/sandbox/{external_id}
        DELETE from DynamoDB
        INCREMENT metrics.cleanup_success
    CATCH:
        INCREMENT retry_count
        IF retry_count > DELETION_RETRY_MAX_ATTEMPTS:
            SET status = 'deletion_failed' (manual intervention)
            ALERT ops team
        INCREMENT metrics.cleanup_failed
```

## Implementation Phases

### ✅ Phase 1: Core FastAPI + Local Development (COMPLETE)
- [x] Set up FastAPI project structure
- [x] Implement core data models (Pydantic schemas for allocation/deletion)
- [x] Create DynamoDB client wrapper
- [x] Implement atomic allocation logic with conditional writes (status='available')
- [x] Add idempotency support (X-Track-ID)
- [x] Local development with DynamoDB Local
- [x] Unit tests for core logic
- [x] Implement POST /v1/allocate with K-candidate strategy
- [x] Implement POST /v1/sandboxes/{id}/mark-for-deletion endpoint
- [x] Implement GET /v1/sandboxes/{id} endpoint
- [x] Implement GET /healthz and /readyz endpoints
- [x] Add authentication via Bearer tokens
- [x] Error handling (401, 403, 404, 409, 5xx)
- [x] Tested and verified (see PHASE1_RESULTS.md)

### Phase 2: Admin Endpoints & Background Jobs ✅
- [x] Implement GET /v1/admin/sandboxes endpoint with pagination (filter by status)
- [x] Implement GET /v1/admin/stats endpoint (pool statistics)
- [x] Implement POST /v1/admin/sync endpoint (trigger ENG sync)
- [x] Implement POST /v1/admin/cleanup endpoint (process pending deletions)
- [x] Add structured JSON logging (request_id, track_id, sandbox_id, action, outcome, latency_ms)
- [x] Admin token authentication (Bearer token)
- [x] ENG CSP service integration (mock implementation)
- [x] Middleware for automatic request/response logging

### Phase 3: Observability & Metrics ✅
- [x] Implement Prometheus metrics endpoint (GET /metrics)
- [x] Add counters: allocate_total, deletion_marked_total, sync_total, cleanup_total, expiry_total
- [x] Add gauges: pool_available, pool_allocated, pool_pending_deletion, pool_stale, pool_deletion_failed, pool_total
- [x] Add histograms: request_latency, allocation_latency, sync_duration, cleanup_duration
- [x] Health check endpoints (/healthz for liveness, /readyz for readiness)
- [x] Background sync job (every 600s, configurable)
- [x] Background cleanup job (every 300s, configurable)
- [x] Background auto-expiry job (every 300s, marks orphaned allocations >4.5h)
- [x] Metrics integration in allocation and admin services
- [x] CloudWatch Logs ready (structured JSON logging from Phase 2)

### Phase 4: Security & Authentication ✅
- [x] Rate limiting middleware (10 RPS sustained, 20 burst, token bucket algorithm)
- [x] Security headers (X-Frame-Options, CSP, HSTS, X-Content-Type-Options, etc.)
- [x] CORS configuration (restrictive, production-ready)
- [x] Circuit breaker for ENG CSP calls (5 failure threshold, 60s timeout)
- [x] Per-client rate limiting (X-Track-ID or IP-based)
- [x] Rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining)
- [x] Health check bypass (no rate limiting for /healthz, /readyz, /metrics)
- [ ] AWS Secrets Manager integration (deferred to Phase 6 - AWS deployment)

### Phase 5: ENG CSP Production Integration ✅
- [x] Real API implementation for fetch_sandboxes (GET /v2/current_user/accounts)
- [x] Real API implementation for delete_sandbox (DELETE /v2/{external_id})
- [x] Mock/production mode auto-detection (based on CSP_API_TOKEN)
- [x] ISO 8601 timestamp parsing for created_at
- [x] Circuit breaker integration for all API calls
- [x] Comprehensive error handling and logging
- [x] Field mapping (csp_id → sandbox_id, id → external_id)
- [x] Filtering for sandbox accounts with state=active
- [x] Documentation (ENG_CSP_INTEGRATION.md with full guide)

### Phase 6: AWS Production Deployment ✅
- [x] Terraform infrastructure (49/49 resources deployed)
- [x] VPC with public/private subnets (multi-AZ in eu-central-1)
- [x] DynamoDB table with 3 GSIs (StatusIndex, TrackIndex, IdempotencyIndex)
- [x] ECS Fargate cluster with auto-scaling (2-10 tasks)
- [x] Application Load Balancer with HTTPS (ACM certificate)
- [x] NAT Gateway with Elastic IP
- [x] VPC endpoints (Secrets Manager, DynamoDB)
- [x] AWS Secrets Manager for tokens (BROKER_API_TOKEN, BROKER_ADMIN_TOKEN, CSP_API_TOKEN)
- [x] CloudWatch log groups (API logs, background jobs)
- [x] IAM roles with least-privilege policies
- [x] EventBridge schedulers for background jobs (sync, cleanup, auto-expiry)
- [x] Security groups with proper ingress/egress rules
- [x] Route53 DNS record (api-sandbox-broker.highvelocitynetworking.com)
- [x] Production URL live: `https://api-sandbox-broker.highvelocitynetworking.com/v1`
- [x] Cost: ~$120-135/month
- [x] Documentation: DEPLOYMENT_STATUS.md, DEPLOYMENT_GUIDE.md

### Phase 7: Testing & Load Testing ✅
- [x] Unit tests (33/33 passing, 100% success rate)
  - [x] Sandbox model tests (5 tests)
  - [x] DynamoDB client tests (13 tests)
  - [x] Allocation service tests (12 tests)
  - [x] Multi-student allocation tests (3 tests - NEW)
- [x] Integration tests (18/20 passing, 2 skipped intentionally)
  - [x] API endpoint tests with mocked services
  - [x] Authentication and authorization tests
  - [x] Admin endpoint tests
- [x] Load test infrastructure
  - [x] K6 multi-student load test script (50 students, 5 labs)
  - [x] DynamoDB seeding utility (no CSP calls)
  - [x] Allocation verification script (zero double-allocation checker)
  - [x] Custom metrics for tracking allocation success/failure
- [x] Multi-student load test execution ✅
  - [x] 200 sandboxes seeded to production DynamoDB
  - [x] 50 concurrent students across 5 labs simulated
  - [x] **ZERO double-allocations verified** (200 students → 200 unique sandboxes)
  - [x] Idempotency verified (same student gets same sandbox)
- [x] Test configuration
  - [x] pytest.ini with async support
  - [x] Coverage reporting (HTML, XML, terminal)
  - [x] Test markers (unit, integration, load, slow)
- [x] Python 3.11 environment setup (fix_test_env.sh)
- [x] Documentation: PHASE7_RESULTS.md (comprehensive test suite documentation)

### Phase 8: CI/CD & Deployment Pipeline
- [ ] GitHub Actions workflow for automated testing
- [ ] Docker image build and push to ECR on merge to main
- [ ] ECS service deployment automation
- [ ] Automated integration tests in CI
- [ ] Blue/green deployment strategy
- [ ] Rollback procedures
- [ ] Secrets management in GitHub Actions

### Phase 9: GameDay Testing & Chaos Engineering
- [ ] Load test execution (1000 RPS target with k6)
- [ ] Chaos testing (ECS task termination during allocation)
- [ ] Pool exhaustion scenarios
- [ ] ENG CSP API outage simulation
- [ ] DynamoDB throttling scenarios
- [ ] Hot partition testing
- [ ] Cleanup failure handling
- [ ] Verify atomic allocation under high concurrency

### Phase 10: Production Hardening & Documentation
- [ ] Operational runbooks for common scenarios
- [ ] Monitoring and alerting setup (CloudWatch Alarms)
- [ ] Cost optimization review
- [ ] Performance tuning based on load test results
- [ ] Security audit (IAM policies, network rules)
- [ ] Disaster recovery procedures
- [ ] Production readiness checklist

## Configuration Parameters
```bash
# API Configuration
BROKER_API_TOKEN                    # Track access bearer token
BROKER_ADMIN_TOKEN                  # Admin operations token
API_BASE_PATH=/v1                   # API version prefix

# DynamoDB Configuration
DDB_TABLE_NAME=SandboxPool
DDB_GSI1_NAME=StatusIndex           # Status + allocated_at
DDB_GSI2_NAME=TrackIndex            # Track + allocated_at
DDB_GSI3_NAME=IdempotencyIndex      # Optional: idempotency_key + allocated_at
DDB_ENDPOINT_URL=                   # Override for local dev (DynamoDB Local)

# Sandbox Lifecycle
LAB_DURATION_HOURS=4                # Max lab duration
GRACE_PERIOD_MINUTES=30             # After expiry before auto-cleanup
SYNC_INTERVAL_SEC=600               # ENG tenant sync (10 min)
CLEANUP_INTERVAL_SEC=300            # Deletion processing (5 min)
AUTO_EXPIRY_INTERVAL_SEC=300        # Check for orphaned allocations (5 min)

# ENG CSP Integration
CSP_BASE_URL=https://eng.csp.example.com
CSP_API_TOKEN                       # ENG CSP authentication
CSP_TIMEOUT_CONNECT_SEC=2
CSP_TIMEOUT_READ_SEC=5

# Concurrency & Resilience
K_CANDIDATES=15                     # Candidate sandboxes to fetch
BACKOFF_BASE_MS=100                 # Initial retry backoff
BACKOFF_MAX_MS=5000                 # Max retry backoff
DELETION_RETRY_MAX_ATTEMPTS=3       # Max retries for ENG CSP delete
CIRCUIT_BREAKER_THRESHOLD=5         # Failures before circuit opens
CIRCUIT_BREAKER_TIMEOUT_SEC=60      # Circuit breaker reset time

# Observability
LOG_LEVEL=INFO                      # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=json                     # json | text
METRICS_PORT=9090                   # Prometheus metrics port
ENABLE_REQUEST_ID=true              # Add X-Request-ID to responses

# AWS Configuration
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=
ECS_CLUSTER_NAME=sandbox-broker
ECS_SERVICE_NAME=sandbox-broker-api
ALB_DNS_NAME=
```

## Error Handling & Edge Cases

### API Error Responses
```json
{
  "error": {
    "code": "NO_SANDBOXES_AVAILABLE",
    "message": "No sandboxes available in pool",
    "request_id": "req_123abc",
    "retry_after": 30  // seconds (optional)
  }
}
```

**Error Codes:**
- `NO_SANDBOXES_AVAILABLE` (409) - Pool exhausted, retry with backoff
- `INVALID_TRACK_ID` (400) - Missing or malformed X-Track-ID header
- `SANDBOX_NOT_FOUND` (404) - Sandbox ID doesn't exist
- `NOT_SANDBOX_OWNER` (403) - Track doesn't own this sandbox
- `ALLOCATION_EXPIRED` (403) - 4-hour window exceeded
- `UNAUTHORIZED` (401) - Invalid or missing bearer token
- `RATE_LIMIT_EXCEEDED` (429) - Too many requests (future)
- `INTERNAL_ERROR` (500) - Unexpected server error
- `SERVICE_UNAVAILABLE` (503) - DynamoDB or ENG CSP unavailable

### Edge Cases & Handling

1. **Double Allocation Prevention**
   - Use DynamoDB conditional write: `status = 'available'`
   - If fails, retry with different candidate
   - After K retries, return 409 with retry_after

2. **Idempotency Collision**
   - Same X-Track-ID requests same sandbox within 4h window
   - Return existing allocation (200 OK) instead of creating new
   - Prevents duplicate allocations on network retries

3. **Sync During Allocation**
   - Sync job NEVER modifies `allocated` or `pending_deletion` status
   - Only upserts `available` and marks missing as `stale`
   - No race conditions between sync and allocation

4. **Cleanup Failure Handling**
   - Track `deletion_retry_count` in DynamoDB
   - Exponential backoff between retries
   - After max attempts, set status=`deletion_failed` and alert
   - Manual intervention required for stuck items

5. **Track Crashes Before Deletion**
   - Auto-expiry job finds allocations >4.5h old
   - Automatically marks as `pending_deletion`
   - Prevents resource leaks

6. **DynamoDB Throttling**
   - Use On-Demand billing initially (auto-scaling)
   - Implement exponential backoff on ProvisionedThroughputExceededException
   - Circuit breaker if sustained throttling

7. **ENG CSP API Outage**
   - Circuit breaker opens after N failures
   - Sync job pauses, system operates on last-known-good pool
   - Cleanup job retries with backoff
   - Resume when circuit closes

## Performance Targets
- Avg allocation latency: <100ms
- 99th percentile: <300ms
- Max concurrent tracks: 1000+
- Sync drift: ≤10 minutes
- Cleanup processing: ≤5 minutes
- DB contention: <2%
- Error budget: 0.1% monthly
- Idempotency hit rate: >80% during retries

## Operational Runbook Scenarios
- **Pool exhaustion** → Increase pool size in ENG CSP; monitor allocation failures; consider shortening lab duration
- **Hot partition** → Raise K and shuffle; verify UUID key entropy
- **Cleanup failures** → Check ENG CSP API health; retry with backoff; query status='deletion_failed' for manual intervention
- **Sync failing** → Circuit open, verify token/endpoint; system operates on last-known-good pool
- **Orphaned allocations** → Auto-expiry job marks after 4.5h; check CloudWatch logs for track failures
- **Student stops early** → Immediate mark-for-deletion call; cleanup within ~5 min (normal happy path)
- **Quarantine sandbox** → Manually set status='stale' to remove from pool
- **Stuck in pending_deletion** → Check deletion_retry_count; investigate ENG CSP API errors; manual delete if needed

## Future Enhancements (Phase 2+)
- Cognito client credentials with scopes
- AWS WAF and IP allowlist
- DynamoDB Global Tables (multi-region)
- SQS/SNS events for allocation/deletion
- S3 audit streaming (allocation history)
- Terraform modules
- API Gateway fronting
- Auto-scaling pool size based on demand
- Sandbox health checks before allocation
