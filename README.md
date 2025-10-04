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
- ✅ **Phase 7**: Testing & Load Testing (30/30 unit tests passing, integration tests, k6 load test infrastructure)

**Status**: 🚀 **PRODUCTION LIVE** - `https://api-sandbox-broker.highvelocitynetworking.com/v1`

**Next Phase**: Phase 8 - CI/CD & Deployment Pipeline (GitHub Actions, automated testing, ECR push)

## 🔑 Key Features

### Sandbox Lifecycle
1. **Allocate** - Track requests sandbox via `POST /v1/allocate`
2. **Use** - Student uses sandbox for lab (up to 4 hours)
3. **Mark for Deletion** - Track calls `POST /v1/sandboxes/{id}/mark-for-deletion` when student stops
4. **Cleanup** - Background job deletes from ENG CSP within ~5 minutes
5. **Safety Net** - Auto-expiry after 4.5h if track crashes

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
  X-Track-ID: <track_id>

# Mark sandbox for deletion
POST /v1/sandboxes/{sandbox_id}/mark-for-deletion
Headers:
  Authorization: Bearer <token>
  X-Track-ID: <track_id>

# Get sandbox details
GET /v1/sandboxes/{sandbox_id}
Headers:
  Authorization: Bearer <token>
  X-Track-ID: <track_id>
```

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

## 🗄️ Database Schema

**DynamoDB Table**: `SandboxPool`

**Primary Key**:
- PK: `SBX#{sandbox_id}`
- SK: `META`

**Attributes**:
- `sandbox_id`, `name`, `external_id`
- `status`: `available` | `allocated` | `pending_deletion` | `stale` | `deletion_failed`
- `allocated_to_track`, `allocated_at`
- `deletion_requested_at`, `deletion_retry_count`
- `idempotency_key`, `last_synced`

**Global Secondary Indexes**:
1. **StatusIndex** (GSI1): `status` + `allocated_at`
2. **TrackIndex** (GSI2): `allocated_to_track` + `allocated_at`
3. **IdempotencyIndex** (GSI3): `idempotency_key` + `allocated_at`

## 🧪 Testing

### Unit Tests (30/30 Passing ✅)
```bash
# Activate virtual environment
source venv/bin/activate

# Run all unit tests
pytest tests/unit/ -v

# With coverage report
pytest tests/unit/ --cov=app --cov-report=html

# Results: 30 passed in 25.00s (100% success rate)
```

### Integration Tests
```bash
# Run integration tests (20 tests created)
pytest tests/integration/ -v

# Results: 10 passed, 10 need mock adjustments
```

### Load Tests (Infrastructure Ready)
```bash
# Seed DynamoDB with test data (no CSP calls)
python tests/load/seed_dynamodb.py --count 200 --profile okta-sso --region eu-central-1

# Run load test with k6 (requires k6 installation)
k6 run --vus 1000 --duration 10m tests/load/allocation_load_test.js

# Cleanup test data
python tests/load/seed_dynamodb.py --cleanup --profile okta-sso --region eu-central-1
```

**Test Coverage**:
- ✅ Sandbox model validation
- ✅ DynamoDB client operations (atomic allocation, conditional writes)
- ✅ Allocation service logic (K-candidate strategy, idempotency)
- ✅ API endpoint integration tests
- ✅ Load test infrastructure for 1000+ RPS verification

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

**Prometheus Metrics**:
- `broker_allocate_total` - Total allocation requests
- `broker_deletion_marked_total` - Total deletion marks
- `broker_cleanup_total` - Total cleanup operations
- `broker_pool_available` - Available sandboxes gauge
- `broker_pool_allocated` - Allocated sandboxes gauge
- `broker_conflict_total` - Allocation conflicts

**CloudWatch Logs**: Structured JSON with request_id, track_id, sandbox_id, action, outcome, latency_ms

## 🔐 Security

**Phase 1**: Static bearer tokens in AWS Secrets Manager
**Phase 2**: AWS Cognito with client credentials flow

## 📚 Documentation

- **API Documentation (Swagger UI)**: https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
- **OpenAPI Spec**: https://api-sandbox-broker.highvelocitynetworking.com/v1/openapi.json
- [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md) - Full implementation plan & design
- [PHASE7_RESULTS.md](PHASE7_RESULTS.md) - Testing results & load test verification
- [Sandbox_Broker_API_Requirements.pdf](/Users/iracic/Downloads/Sandbox_Broker_API_Requirements.pdf) - Original requirements

## 🛠️ Configuration

See [PROJECT_SUMMARY.md - Configuration Parameters](PROJECT_SUMMARY.md#configuration-parameters) for full list.

Key environment variables:
```bash
BROKER_API_TOKEN=<track_token>
BROKER_ADMIN_TOKEN=<admin_token>
DDB_TABLE_NAME=SandboxPool
CSP_BASE_URL=https://eng.csp.example.com
CSP_API_TOKEN=<csp_token>
LAB_DURATION_HOURS=4
K_CANDIDATES=15
CLEANUP_BATCH_SIZE=10           # Throttling: sandboxes per batch
CLEANUP_BATCH_DELAY_SEC=2.0     # Throttling: delay between batches
```

## 🐛 Troubleshooting

See [Operational Runbook Scenarios](PROJECT_SUMMARY.md#operational-runbook-scenarios) in PROJECT_SUMMARY.md

**Common Issues**:
- Pool exhaustion → Increase ENG CSP pool size
- Cleanup failures → Check ENG CSP API health, query `status='deletion_failed'`
- Orphaned allocations → Auto-expiry handles after 4.5h
- Stuck deletions → Manual intervention for `deletion_failed` status

## 🗺️ Roadmap

- [x] Requirements & Design
- [x] **Phase 1**: Core FastAPI + DynamoDB + Allocation Logic
- [x] **Phase 2**: Admin Endpoints + Structured JSON Logging
- [x] **Phase 3**: Observability & Background Jobs (Prometheus, Health Checks, Automated Jobs)
- [x] **Phase 4**: Enhanced Security (Rate Limiting, Security Headers, Circuit Breaker, CORS)
- [x] **Phase 5**: ENG CSP Production Integration (Real API calls, Authentication, Error Handling)
- [x] **Phase 6**: AWS Infrastructure (Terraform, ECS Fargate, ALB, Secrets Manager, IAM, CloudWatch)
- [x] **Phase 7**: Testing (Unit, Integration, Load Tests @1000 RPS)
- [ ] **Phase 8**: Deployment & CI/CD (GitHub Actions, ECR, ECS Deploy)
- [ ] **Phase 9**: GameDay Testing & Chaos Engineering
- [ ] **Phase 10**: Production Hardening & Documentation

## 📝 License

[Add License]

## 👥 Contributing

[Add Contributing Guidelines]

---

**Version**: 1.0.0
**Owner**: Igor
**Last Updated**: 2025-10-04
