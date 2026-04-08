# Sandbox Broker API

> High-concurrency AWS-based API for allocating pre-created CSP sandboxes to Instruqt tracks at scale (1000+ concurrent requests)

## 🎯 Project Goal

Build a high-performance, concurrent-safe Sandbox Broker API that allocates pre-created sandboxes from the ENG tenant to Instruqt tracks, ensuring zero double-allocations and immediate cleanup when students stop labs.

## 🏗️ Architecture

- **API**: FastAPI (async) on ECS Fargate
- **Database**: DynamoDB with GSIs for atomic operations
- **Load Balancer**: ALB with HTTPS
- **Sync**: EventBridge Scheduler → ECS Task/Lambda
- **Observability**: CloudWatch + Prometheus metrics

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- AWS Account (for deployment)

### Local Development with Docker Compose

```bash
# Clone repository
git clone <repo-url>
cd Sandbox-API-Broker

# Start services (DynamoDB Local + API)
docker compose up -d

# Initialize database and seed test data
docker cp init_and_seed.py sandbox-broker-api:/app/
docker exec sandbox-broker-api python /app/init_and_seed.py

# View API logs
docker compose logs -f api

# API available at http://localhost:8080
# DynamoDB Local at http://localhost:8000
# API docs at http://localhost:8080/v1/docs
```

### Manual Setup (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Run DynamoDB Local
docker run -p 8000:8000 amazon/dynamodb-local

# Run the API
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

## 📋 Project Status

See [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) for detailed implementation plan and progress tracking.

**Completed Phases**:
- ✅ **Phase 1**: Core FastAPI + DynamoDB (allocation, deletion, idempotency)
- ✅ **Phase 2**: Admin Endpoints + Structured Logging (list, sync, cleanup, stats)
- ✅ **Phase 3**: Observability & Background Jobs (Prometheus metrics, health checks, automated jobs)
- ✅ **Phase 4**: Enhanced Security & Resilience (rate limiting, security headers, circuit breaker, CORS)
- ✅ **Phase 5**: ENG CSP Production Integration (real API calls, mock/production mode, error handling)
- ✅ **Phase 6**: AWS Production Deployment (49/49 resources, HTTPS, multi-AZ, auto-scaling)
- ✅ **Phase 7**: Testing & Load Testing (53/53 tests passing, multi-student load test with ZERO double-allocations)
- ✅ **Phase 8**: Production Fixes & Worker Service (rate limiter fix, CORS updates, worker service separation, metrics caching)

**Status**: 🚀 **PRODUCTION LIVE** - `https://api-sandbox-broker.highvelocitynetworking.com/v1`

**Latest Deployment**: 2026-04-08 - SFDC Account ID, NIOSXaaS cleanup, Instruqt lifecycle scripts, 48h lab duration

**Dashboard**: https://broker-dashboard.highvelocitynetworking.com

**Instruqt Scripts** (`scripts/`): `allocation_broker_subtenant.py` → `user_provision.py` → `user_cleanup.py` → `deallocation_broker_subtenant.py`

**Next Phase**: Phase 9 - GameDay Testing & Chaos Engineering

## 🔑 Key Features

### Sandbox Lifecycle
1. **Allocate** - Track requests sandbox via `POST /v1/allocate`
2. **Use** - Student uses sandbox for lab (up to 4 hours)
3. **Mark for Deletion** - Track calls `POST /v1/sandboxes/{id}/mark-for-deletion` when student stops
4. **NIOSXaaS Cleanup** - Background job deletes NIOSXaaS universal services from sandbox account
5. **CSP Deletion** - Background job deletes sandbox from ENG CSP within ~5 minutes
6. **Safety Net** - Auto-expiry after 48.5h if track crashes

### NIOSXaaS Cleanup (New)

When sandboxes are deleted, any NIOSXaaS universal services created within them would be orphaned. The cleanup process automatically:

1. Authenticates with CSP using service account credentials
2. Switches to the sandbox account context
3. Lists all universal services in the sandbox
4. Deletes services matching the configured name filter (default: `Instrqt-SaaS`)
5. Logs cleanup result (success/skipped/failed) for dashboard statistics

**Key Features:**
- **Non-blocking**: NIOSXaaS failures don't prevent CSP sandbox deletion
- **Circuit breaker**: Protects against cascading failures
- **Shadow mode**: Test without actual deletions
- **Statistics**: Dashboard shows cleanup metrics (Cleaned, Skipped, Failed, Pending)
- **TTL**: Cleanup records auto-delete after 30 days

### Concurrency Strategy
- **Atomic allocation** via DynamoDB conditional writes
- **K-candidate fan-out** (fetch 10-20 sandboxes, shuffle to avoid thundering herd)
- **Idempotency** via X-Track-ID header (safe retries)
- **Zero double-allocations** guaranteed

### Performance Targets
- Avg allocation latency: <100ms
- 99th percentile: <300ms
- Max concurrent tracks: 1000+
- Cleanup latency: ~5 minutes

## 📡 API Endpoints

### Track Endpoints
```bash
# Allocate a sandbox
POST /v1/allocate
Headers:
  Authorization: Bearer <token>
  X-Instruqt-Sandbox-ID: <unique_sandbox_id>     # REQUIRED - unique per student
  X-Instruqt-Track-ID: <lab_identifier>          # OPTIONAL - for analytics/grouping

  # Legacy format (backward compatible):
  # X-Track-ID: <unique_sandbox_id>              # REQUIRED - unique per student

Response:
  {
    "sandbox_id": "2026839",
    "name": "lab-adventure-0087",
    "external_id": "1e96e538-f8f1-4d52-8778-a122c284f03c",  # Use this to connect to CSP
    "allocated_at": 1728054123,
    "expires_at": 1728054123,
    "sfdc_account_id": "001SAND122c284f03c"
  }

# Mark sandbox for deletion
POST /v1/sandboxes/{sandbox_id}/mark-for-deletion
Headers:
  Authorization: Bearer <token>
  X-Instruqt-Sandbox-ID: <unique_sandbox_id>     # REQUIRED
  # OR X-Track-ID: <unique_sandbox_id>           # Legacy

# Get sandbox details
GET /v1/sandboxes/{sandbox_id}
Headers:
  Authorization: Bearer <token>
  X-Instruqt-Sandbox-ID: <unique_sandbox_id>     # REQUIRED
  # OR X-Track-ID: <unique_sandbox_id>           # Legacy
```

**Important Notes:**
- `X-Instruqt-Sandbox-ID` must be the **unique Instruqt sandbox instance ID** (unique per student), NOT the lab/track identifier
- Multiple students can run the same lab simultaneously - each gets a different sandbox
- `X-Instruqt-Track-ID` is optional - stored as `track_name` for analytics (allows querying "which sandboxes are for lab X")
- The `external_id` in the response is the CSP UUID needed to connect to the actual sandbox

### Admin Endpoints
```bash
# List all sandboxes with filtering and pagination
GET /v1/admin/sandboxes?status=available&limit=50&cursor=<base64_cursor>
Headers:
  Authorization: Bearer <admin_token>

# Get pool statistics
GET /v1/admin/stats
Headers:
  Authorization: Bearer <admin_token>

# Trigger ENG CSP sync
POST /v1/admin/sync
Headers:
  Authorization: Bearer <admin_token>

# Process pending deletions
POST /v1/admin/cleanup
Headers:
  Authorization: Bearer <admin_token>

# Bulk delete sandboxes by status (manual cleanup)
POST /v1/admin/bulk-delete?status=stale
Headers:
  Authorization: Bearer <admin_token>
# Use cases:
# - Clean up stale sandboxes immediately (before 24h auto-cleanup)
# - Remove deletion_failed sandboxes after manual CSP cleanup
# Note: Stale sandboxes are automatically deleted after 24 hours by background job
```

### Observability
```bash
# Health check (liveness probe)
GET /healthz
# Returns: {"status": "healthy", "timestamp": 1759574955}

# Readiness check (DynamoDB connectivity)
GET /readyz
# Returns: {"status": "ready", "checks": {"dynamodb": "ok"}}

# Prometheus metrics
GET /metrics
# Returns: Prometheus exposition format with 20+ metrics
# - Counters: allocate_total, sync_total, cleanup_total, expiry_total
# - Gauges: pool_available, pool_allocated, pool_total
# - Histograms: request_latency, allocation_latency
```

## ⚡ Rate Limits and API Constraints

### Application Rate Limits (Token Bucket)

The API uses a token bucket rate limiting algorithm to protect against abuse and ensure fair resource allocation:

**Current Configuration:**
- **Sustained Rate**: 50 requests per second
- **Burst Capacity**: 200 concurrent requests
- **Scope**: Per client IP (as seen by the ALB)

**How It Works:**
```
Bucket starts with 200 tokens (burst capacity)
├─ Each request consumes 1 token
├─ Tokens refill at 50/second
└─ Full capacity restored in ~4 seconds
```

**Performance Characteristics:**

| Scenario | Result | Notes |
|----------|--------|-------|
| 200 students allocate at once | ✅ All succeed immediately | Burst capacity |
| 400 students over 10 seconds | ✅ All succeed | 200 burst + 300 refilled (50/s × 6s) |
| 500 students over 15 seconds | ✅ All succeed | 200 burst + 600 refilled (50/s × 12s) |
| 300 requests instantly | ⚠️ 100 get 429 errors | Exceeds burst capacity |

**Rate Limit Headers:**
```
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 157
X-RateLimit-Reset: 1696512345
```

**429 Response Example:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Retry after 2 seconds.",
    "retry_after": 2,
    "request_id": "abc123..."
  }
}
```

### AWS WAF Rate Limits

**Additional protection layer at the load balancer:**
- **Limit**: 2000 requests per 5 minutes per source IP
- **Scope**: Per IP address (before ALB)
- **Response**: 403 Forbidden

**Important Note:** Each Instruqt student typically comes from a different IP, so each gets their own 2000 req/5min allowance. This limit primarily affects:
- Load testing from a single machine
- Misbehaving scripts/bots
- Distributed attacks

### Single IP Behavior

**How Source IP Works:**
1. **External requests** → ALB sees original client IP (X-Forwarded-For)
2. **WAF rate limiting** → Applied per original client IP
3. **Application rate limiting** → Applied per original client IP
4. **ECS tasks** → All tasks share the same rate limit state (via DynamoDB/memory)

**Key Implications:**
- Multiple students from different IPs → Each gets full rate limit allowance
- Multiple students from same IP (same organization/NAT) → Share rate limit allowance
- Load testing from one machine → Hits single IP limits quickly

### Best Practices for Handling Rate Limits

**1. Implement Exponential Backoff:**
```python
import time
import random

def allocate_with_retry(max_retries=3):
    for attempt in range(max_retries):
        response = requests.post(API_URL, headers=headers)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            retry_after = response.json()["error"].get("retry_after", 2)
            sleep_time = retry_after * (2 ** attempt) + random.uniform(0, 1)
            time.sleep(sleep_time)
        else:
            raise Exception(f"Unexpected error: {response.status_code}")

    raise Exception("Max retries exceeded")
```

**2. Monitor Rate Limit Headers:**
```python
remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
if remaining < 10:
    print("Warning: Approaching rate limit")
    time.sleep(1)  # Slow down requests
```

**3. Batch Requests When Possible:**
- Avoid polling endpoints repeatedly
- Use webhooks instead of polling where possible
- Cache sandbox details instead of repeated GET requests

**4. Request Limit Increases:**
If your use case requires higher limits, contact the API administrators with:
- Expected peak concurrent users
- Average requests per student session
- Geographic distribution of users

### DynamoDB Capacity

**Current Configuration:**
- **Mode**: On-Demand (auto-scales)
- **Write Capacity**: Auto-scales up to 40,000 WCU
- **Read Capacity**: Auto-scales up to 40,000 RCU

**Typical Usage:**
- Allocation: 2 writes (conditional update + idempotency), 1-3 reads
- Mark for deletion: 1 write, 1 read
- Sync job: Batch reads (25 per page)

**Throttling:** Very rare with on-demand mode, but possible during extreme spikes (>1000 RPS sustained).

## 🗄️ Database Schema

**DynamoDB Table**: `sandbox-broker-pool`

### Sandbox Records (SBX#)

**Primary Key**:
- PK: `SBX#{sandbox_id}`
- SK: `META`

**Attributes**:
- `sandbox_id`, `name`, `external_id`, `sfdc_account_id`
- `status`: `available` | `allocated` | `pending_deletion` | `stale` | `deletion_failed`
- `allocated_to_track`, `allocated_at`
- `deletion_requested_at`, `deletion_retry_count`
- `idempotency_key`, `last_synced`
- `niosxaas_cleaned_at`, `niosxaas_cleanup_skipped`, `niosxaas_cleanup_failed_reason` (cleanup tracking)

### NIOSXaaS Cleanup Records (NIOSXAAS#)

**Primary Key**:
- PK: `NIOSXAAS#{sandbox_id}`
- SK: `CLEANUP`

**Attributes**:
- `sandbox_id`, `sandbox_name`, `external_id`, `track_name`
- `niosxaas_cleaned_at`, `niosxaas_cleanup_skipped`, `niosxaas_cleanup_failed_reason`
- `deleted_at` - when CSP sandbox was deleted
- `ttl` - auto-delete after 30 days (DynamoDB TTL)

These records preserve cleanup statistics after sandbox deletion for dashboard reporting.

**Global Secondary Indexes**:
1. **StatusIndex** (GSI1): `status` + `allocated_at`
2. **TrackIndex** (GSI2): `allocated_to_track` + `allocated_at`
3. **IdempotencyIndex** (GSI3): `idempotency_key` + `allocated_at`

## 🧪 Testing

### Unit Tests (33/33 Passing ✅)
```bash
# Activate virtual environment
source venv/bin/activate

# Run all unit tests
pytest tests/unit/ -v

# With coverage report
pytest tests/unit/ --cov=app --cov-report=html

# Results: 33 passed (includes multi-student scenarios)
```

### Integration Tests (18/20 Passing ✅)
```bash
# Run integration tests
pytest tests/integration/ -v

# Results: 18 passed, 2 skipped (intentional)
```

### Load Tests (Multi-Student Verified ✅)
```bash
# Seed DynamoDB with test data (no CSP calls)
python tests/load/seed_dynamodb.py --count 200 --region eu-central-1

# Run multi-student load test (50 students, 5 labs)
k6 run --vus 50 --duration 2m tests/load/multi_student_load_test.js

# Verify zero double-allocations
python tests/load/verify_allocations.py --region eu-central-1
# Results: 200 unique students → 200 unique sandboxes, ZERO double-allocations ✅

# Cleanup test data
python tests/load/seed_dynamodb.py --cleanup --region eu-central-1
```

**⚠️ Important: AWS WAF Rate Limiting During Load Tests**

When running load tests from a single IP address, you may hit the AWS WAF rate limit (2000 requests per 5 minutes per IP). This will cause 403 Forbidden errors and is **expected behavior** - the WAF is protecting your API from abuse.

**Symptoms:**
- High percentage of 403 Forbidden responses during load tests
- Requests succeed initially, then get blocked
- 5-minute cooldown period after hitting the limit

**Solutions for load testing:**
1. **Temporarily disable WAF rate limiting** (not recommended for production)
2. **Whitelist your IP** in WAF rules during testing
3. **Use distributed load testing** (k6 cloud, AWS distributed load testing)
4. **Reduce concurrency** to stay under the limit (e.g., 50 VUs instead of 100)

**In production:** Each real user comes from a different IP address, so each gets their own 2000 req/5min allowance. This won't impact normal operations.

**Test Coverage**:
- ✅ Sandbox model validation
- ✅ DynamoDB client operations (atomic allocation, conditional writes)
- ✅ Allocation service logic (K-candidate strategy, idempotency)
- ✅ API endpoint integration tests
- ✅ Multi-student same-lab scenarios (verified with load tests)
- ✅ Zero double-allocations verified (200 concurrent students)

## 🚢 Deployment

### Local Development
See [Quick Start](#-quick-start) section above.

### AWS Production Deployment

✅ **Currently Deployed**: The API is live on AWS ECS Fargate in eu-central-1 (Frankfurt).

**Production URL**: `https://api-sandbox-broker.highvelocitynetworking.com/v1`

**Deployment Status**: See [DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md) for complete details.

**Infrastructure (49/49 resources deployed)**:
- ✅ VPC with public/private subnets (multi-AZ)
- ✅ ECS Fargate cluster with auto-scaling (2-10 tasks)
- ✅ Application Load Balancer with HTTPS (ACM certificate)
- ✅ DynamoDB table with 3 GSIs (fixed schema)
- ✅ VPC endpoints (Secrets Manager, DynamoDB)
- ✅ NAT Gateway with Elastic IP
- ✅ AWS Secrets Manager for tokens
- ✅ CloudWatch log groups
- ✅ IAM roles with least-privilege policies
- ✅ EventBridge schedulers for background jobs

**Cost**: ~$120-135/month (eu-central-1)

**To deploy your own instance:**
```bash
# Build and push Docker image to ECR
docker build --platform linux/amd64 -t sandbox-broker-api .
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.eu-central-1.amazonaws.com
docker tag sandbox-broker-api:latest <account>.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api:latest
docker push <account>.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api:latest

# Deploy infrastructure with Terraform
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your configuration
terraform init
terraform apply
```

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for step-by-step deployment instructions.

## 📊 Metrics & Monitoring

### Comprehensive Observability

**See [OBSERVABILITY.md](OBSERVABILITY.md) for complete troubleshooting guide**

**CloudWatch Logs** (30-day retention):
- API logs: `/ecs/sandbox-broker`
- Worker logs: `/ecs/sandbox-broker-worker`
- Structured JSON format with request_id, action, outcome, latency_ms

**Metric Filters** (6 configured):
- `APIErrors` - Track all API errors
- `NoSandboxesAvailable` - Pool exhaustion alerts
- `HighLatencyRequests` - Performance monitoring (>1s)
- `WorkerErrors` - Background job failures
- `WorkerJobFailures` - Job-specific errors
- `CSPAPIErrors` - CSP integration issues

**CloudWatch Insights Queries** (6 saved):
- All Errors - Quick error investigation
- Allocation Failures - Debug allocation issues
- Slow Requests - Performance troubleshooting
- Worker Jobs - Monitor background jobs
- Rate Limit Hits - Identify clients hitting limits
- CSP API Calls - Debug CSP integration

**Prometheus Metrics**:
- `broker_allocate_total` - Total allocation requests
- `broker_deletion_marked_total` - Total deletion marks
- `broker_cleanup_total` - Total cleanup operations
- `broker_pool_available` - Available sandboxes gauge
- `broker_pool_allocated` - Allocated sandboxes gauge
- `broker_conflict_total` - Allocation conflicts
- `http_request_duration_seconds` - Request latency histogram
- `niosxaas_cleanup_total{outcome}` - NIOSXaaS cleanup attempts (success/skipped/failed/error)
- `niosxaas_services_deleted_total` - Total NIOSXaaS services deleted
- `niosxaas_auth_total{outcome}` - NIOSXaaS authentication attempts
- Plus 20+ additional metrics

**Quick Status Check**:
```bash
# Check pool status
curl -s https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep broker_pool

# Check ECS services
aws ecs describe-services --cluster sandbox-broker-cluster \
  --services sandbox-broker sandbox-broker-worker \
  --region eu-central-1 --profile okta-sso \
  --query 'services[*].{Name:serviceName,Running:runningCount,Desired:desiredCount}' \
  --output table
```

## 🔐 Security

**Phase 1**: Static bearer tokens in AWS Secrets Manager
**Phase 2**: AWS Cognito with client credentials flow

## 📚 Documentation

### API Documentation
- **Swagger UI**: https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
- **OpenAPI Spec**: https://api-sandbox-broker.highvelocitynetworking.com/v1/openapi.json

### Operational Guides
- [OBSERVABILITY.md](OBSERVABILITY.md) - Complete troubleshooting & monitoring guide
- [ROLLBACK_PLAN.md](ROLLBACK_PLAN.md) - Emergency rollback procedures
- [DEPLOYMENT_SUCCESS.md](DEPLOYMENT_SUCCESS.md) - Latest deployment report (2025-10-08)
- [TEST_SUMMARY.md](TEST_SUMMARY.md) - Test results (53/53 passing)

### Design & Implementation
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Full implementation plan & design
- [FIXES_SUMMARY.md](FIXES_SUMMARY.md) - Production fixes changelog
- [DATABASE_SCHEMA.md](DATABASE_SCHEMA.md) - DynamoDB schema details
- [API_LIMITS.md](API_LIMITS.md) - Rate limits and constraints

### Requirements
- [Sandbox_Broker_API_Requirements.pdf](/Users/iracic/Downloads/Sandbox_Broker_API_Requirements.pdf) - Original requirements

## 🛠️ Configuration

See [PROJECT_SUMMARY.md - Configuration Parameters](PROJECT_SUMMARY.md#configuration-parameters) for full list.

Key environment variables:
```bash
# Core Configuration
BROKER_API_TOKEN=<track_token>
BROKER_ADMIN_TOKEN=<admin_token>
DDB_TABLE_NAME=SandboxPool
CSP_BASE_URL=https://eng.csp.example.com
CSP_API_TOKEN=<csp_token>
LAB_DURATION_HOURS=48
K_CANDIDATES=15

# Cleanup Throttling
CLEANUP_BATCH_SIZE=10                 # Sandboxes per batch
CLEANUP_BATCH_DELAY_SEC=30.0          # Delay between batches
CLEANUP_PER_SANDBOX_DELAY_SEC=30.0    # Delay between individual deletions

# NIOSXaaS Cleanup (Worker only)
NIOSXAAS_ENABLED=true                 # Enable NIOSXaaS cleanup
NIOSXAAS_BASE_URL=https://csp.infoblox.com
NIOSXAAS_EMAIL=<from_secrets_manager> # Service account email
NIOSXAAS_PASSWORD=<from_secrets_manager> # Service account password
NIOSXAAS_SERVICE_NAME=Instrqt-SaaS    # Filter by service name (empty = all)
NIOSXAAS_TIMEOUT_SEC=30               # API timeout per operation
NIOSXAAS_SHADOW_MODE=false            # Log only, don't delete (for testing)
```

## 🐛 Troubleshooting

**See [OBSERVABILITY.md](OBSERVABILITY.md) for comprehensive troubleshooting guide**

### Quick Diagnostics

```bash
# 1. Check API health
curl https://api-sandbox-broker.highvelocitynetworking.com/healthz

# 2. Check pool status
curl -s https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep broker_pool

# 3. Check for errors
aws logs tail /ecs/sandbox-broker --since 10m --region eu-central-1 --profile okta-sso | grep ERROR

# 4. Run saved CloudWatch Insights query
# Go to CloudWatch Console → Insights → Saved queries → "Sandbox-Broker-All-Errors"
```

**Common Issues**:
- **Pool exhaustion** → Check `broker_pool_available` metric, increase CSP pool size
- **Cleanup failures** → Run "Worker Jobs" Insights query, check CSP API health
- **Orphaned allocations** → Auto-expiry handles after 48.5h
- **High latency** → Run "Slow Requests" Insights query, check DynamoDB throttling
- **Worker not running** → Check ECS service status, verify 1 task running
- **Pause deletions during CSP outage** → See `WORKER_FREEZE_RUNBOOK.md` to scale worker to 0 and resume

**CloudWatch Insights Queries**: 6 saved queries available in CloudWatch Console for instant troubleshooting

## 🗺️ Roadmap

- [x] Requirements & Design
- [x] **Phase 1**: Core FastAPI + DynamoDB + Allocation Logic
- [x] **Phase 2**: Admin Endpoints + Structured JSON Logging
- [x] **Phase 3**: Observability & Background Jobs (Prometheus, Health Checks, Automated Jobs)
- [x] **Phase 4**: Enhanced Security (Rate Limiting, Security Headers, Circuit Breaker, CORS)
- [x] **Phase 5**: ENG CSP Production Integration (Real API calls, Authentication, Error Handling)
- [x] **Phase 6**: AWS Infrastructure (Terraform, ECS Fargate, ALB, Secrets Manager, IAM, CloudWatch)
- [x] **Phase 7**: Testing (53/53 tests passing, Load Tests, Zero Double-Allocations)
- [x] **Phase 8**: Production Fixes & Worker Service (Rate limiter, CORS, Metrics caching, Worker separation)
- [ ] **Phase 9**: GameDay Testing & Chaos Engineering
- [ ] **Phase 10**: CI/CD Pipeline (GitHub Actions, ECR, ECS Deploy)

## 📝 License

[Add License]

## 👥 Contributing

[Add Contributing Guidelines]

---

**Version**: 1.6.0 (SFDC Account ID + Instruqt Scripts + 48h Lab Duration)
**Owner**: Igor Racic
**Last Updated**: 2026-04-08
**Production Status**: ✅ LIVE - API healthy, worker paused (CSP maintenance)
