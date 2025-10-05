# Sandbox Broker API - Complete Project Summary

**Date**: 2025-10-05
**Status**: 🚀 **PRODUCTION LIVE** with Multi-Student Support
**Production URL**: https://api-sandbox-broker.highvelocitynetworking.com/v1
**GitHub**: https://github.com/iracic82/Sandbox-API-Broker

---

## 🎯 Project Overview

High-concurrency API broker that allocates pre-created CSP sandboxes to Instruqt students with:
- ✅ **Zero double-allocations** (atomic DynamoDB operations)
- ✅ **Multi-student support** (multiple students, same lab, different sandboxes)
- ✅ **Auto-expiry safety net** (4.5 hour cleanup)
- ✅ **AWS WAF protection** (OWASP rules + rate limiting)
- ✅ **Production hardened** (HTTPS, multi-AZ, auto-scaling)

---

## ✅ Completed Phases (1-7)

### Phase 1: Core Implementation ✅
- FastAPI with async support
- DynamoDB with 3 GSIs (StatusIndex, TrackIndex, IdempotencyIndex)
- K-candidate allocation strategy (fetch 15, shuffle, atomic allocate)
- Idempotency via header-based keys
- Sandbox lifecycle: available → allocated → pending_deletion

### Phase 2: Admin & Logging ✅
- Admin endpoints: `/admin/sandboxes`, `/admin/stats`, `/admin/sync`, `/admin/cleanup`
- Structured JSON logging with request_id, track_id, latency_ms
- Pagination with cursor-based continuation

### Phase 3: Observability & Background Jobs ✅
- Prometheus metrics (20+ counters, gauges, histograms)
- Health checks: `/healthz` (liveness), `/readyz` (readiness)
- Background jobs via EventBridge Scheduler:
  - Sync job: Every 10 minutes (pull new sandboxes from CSP)
  - Cleanup job: Every 5 minutes (delete pending_deletion sandboxes)
  - Auto-expiry job: Every 5 minutes (mark expired allocations)

### Phase 4: Security & Resilience ✅
- Rate limiting: slowapi (100 req/min per IP for /allocate)
- Security headers: HSTS, CSP, X-Frame-Options, X-Content-Type-Options
- Circuit breaker for CSP API calls (5 failures → open circuit)
- CORS with restricted methods and headers

### Phase 5: ENG CSP Integration ✅
- Real API calls to `https://csp.infoblox.com/v2`
- Mock mode for development (env var: `USE_MOCK_CSP=true`)
- Error handling with exponential backoff
- Throttled cleanup: 10 sandboxes/batch, 2-second delay

### Phase 6: AWS Production Deployment ✅
- **Infrastructure**: 51/51 Terraform resources deployed
  - VPC: Public/private subnets, NAT Gateway, Internet Gateway
  - ECS Fargate: Auto-scaling (2-10 tasks), multi-AZ
  - ALB: HTTPS with ACM certificate, health checks
  - DynamoDB: On-demand capacity, point-in-time recovery
  - VPC Endpoints: Secrets Manager, DynamoDB (no internet exposure)
  - AWS Secrets Manager: API tokens, CSP token
  - IAM: Least-privilege roles for ECS tasks
  - EventBridge: Scheduled ECS tasks for background jobs
  - **AWS WAF**: Managed rules + rate limiting (2000 req/5min per IP)
- **Region**: eu-central-1 (Frankfurt)
- **Cost**: ~$120-135/month

### Phase 7: Testing & Validation ✅
- **Unit Tests**: 33/33 passing
  - Original: 30 tests (allocation, DynamoDB, models)
  - New: 3 tests (multi-student scenarios)
- **Integration Tests**: 18/20 passing (2 skipped)
- **Load Tests**: Infrastructure ready with k6
  - Smoke test: 10 VUs, 30s → p95=50ms, p99=69ms
  - Stress test: 100 VUs, 2 min → **ZERO double-allocations verified**
- **E2E Test**: Real CSP API tested with throttling

---

## 🎯 Latest Addition: Multi-Student Support (2025-10-05)

### Problem Solved
**Before**: All students in the same lab shared one `track_id` → collision/overwrite risk
**After**: Each student gets unique `sandbox_id` → multiple students, same lab, different sandboxes

### API Changes (Backward Compatible)

**New Headers (Preferred):**
```bash
POST /v1/allocate
Headers:
  Authorization: Bearer <token>
  X-Instruqt-Sandbox-ID: <unique_per_student>     # REQUIRED - unique sandbox instance
  X-Instruqt-Track-ID: <lab_name>                 # OPTIONAL - for analytics
```

**Legacy Headers (Still Supported):**
```bash
POST /v1/allocate
Headers:
  Authorization: Bearer <token>
  X-Track-ID: <unique_per_student>                # REQUIRED - legacy format
```

### Implementation Details
- **Header Extraction**: `app/api/dependencies.py` - Fallback logic (new → legacy)
- **All Endpoints Updated**: allocate, mark-for-deletion, get sandbox
- **Enhanced Logging**: Both sandbox_id and track_id logged for analytics
- **Zero Breaking Changes**: Legacy headers still work

### Testing
- ✅ Test 1: Multiple students, same lab → different sandboxes
- ✅ Test 2: Same student, multiple requests → same sandbox (idempotency)
- ✅ Test 3: Legacy header backward compatibility

---

## 📊 Current Production Stats

### Infrastructure
- **VPC**: vpc-07fbb704dcf4a7371
- **ECS Cluster**: sandbox-broker-cluster (2 tasks running)
- **ALB**: sandbox-broker-alb-370737173.eu-central-1.elb.amazonaws.com
- **DynamoDB Table**: sandbox-broker-pool
- **WAF Web ACL**: c127b4d7-17bf-4a0c-b89a-8e6ca44eca8f

### Endpoints
- **API**: https://api-sandbox-broker.highvelocitynetworking.com/v1
- **Swagger**: https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
- **OpenAPI**: https://api-sandbox-broker.highvelocitynetworking.com/v1/openapi.json
- **Health**: https://api-sandbox-broker.highvelocitynetworking.com/healthz
- **Metrics**: https://api-sandbox-broker.highvelocitynetworking.com/metrics

### Performance
- **Allocation Latency**: p95 = 50ms, p99 = 69ms
- **Concurrency**: Verified at 100 concurrent requests
- **Double-Allocations**: ZERO (DynamoDB atomic operations)
- **Cleanup**: ~7 seconds per sandbox (with throttling)

---

## 🔐 Security Features

### Application Layer
- ✅ Bearer token authentication (AWS Secrets Manager)
- ✅ Rate limiting: 100 req/min per IP for /allocate
- ✅ Security headers: HSTS, CSP, X-Frame-Options, X-XSS-Protection
- ✅ CORS: Restricted origins, methods, headers
- ✅ Input validation: Pydantic models
- ✅ Circuit breaker: CSP API protection

### Infrastructure Layer
- ✅ **AWS WAF**: OWASP Top 10 + Known Bad Inputs + Rate Limiting (2000 req/5min)
- ✅ Private subnets: ECS tasks isolated from internet
- ✅ VPC endpoints: Secrets Manager, DynamoDB (no internet exposure)
- ✅ HTTPS only: ACM certificate with ALB
- ✅ Security groups: Least-privilege rules
- ✅ IAM roles: Minimal permissions

---

## 📁 Key Files Reference

### Core Application
| File | Purpose | Lines |
|------|---------|-------|
| `app/main.py` | FastAPI app entry point, Swagger docs | 173 |
| `app/api/routes.py` | Track endpoints (allocate, mark-for-deletion, get) | 211 |
| `app/api/admin_routes.py` | Admin endpoints (list, stats, sync, cleanup) | 144 |
| `app/api/dependencies.py` | Header extraction, authentication | 91 |
| `app/services/allocation.py` | K-candidate allocation logic | 227 |
| `app/services/admin.py` | Background jobs (sync, cleanup, expiry) | 290 |
| `app/services/eng_csp.py` | ENG CSP API client with circuit breaker | 204 |
| `app/db/dynamodb.py` | DynamoDB client, atomic operations | 291 |
| `app/models/sandbox.py` | Sandbox domain model | 79 |
| `app/middleware/logging.py` | Request/response logging | 79 |
| `app/middleware/security.py` | Security headers (CSP fix for Swagger) | 53 |
| `app/middleware/rate_limit.py` | Rate limiting with slowapi | 152 |

### Infrastructure
| File | Purpose | Resources |
|------|---------|-----------|
| `terraform/vpc.tf` | VPC, subnets, NAT, IGW | 10 |
| `terraform/ecs.tf` | ECS cluster, service, task definition, auto-scaling | 9 |
| `terraform/alb.tf` | Application Load Balancer, target group, listeners | 5 |
| `terraform/dynamodb.tf` | DynamoDB table with 3 GSIs | 1 |
| `terraform/secrets.tf` | AWS Secrets Manager for tokens | 6 |
| `terraform/iam.tf` | IAM roles and policies | 8 |
| `terraform/eventbridge.tf` | Background job schedulers | 3 |
| `terraform/waf.tf` | AWS WAF with managed rules | 2 |
| `terraform/vpc_endpoints.tf` | VPC endpoints for Secrets Manager, DynamoDB | 2 |
| `terraform/cloudwatch.tf` | CloudWatch log groups | 2 |

### Testing
| File | Purpose | Tests |
|------|---------|-------|
| `tests/unit/test_allocation_service.py` | Allocation logic tests | 11 |
| `tests/unit/test_dynamodb_client.py` | DynamoDB client tests | 13 |
| `tests/unit/test_sandbox_model.py` | Sandbox model tests | 5 |
| `tests/unit/test_multi_student_allocation.py` | Multi-student scenario tests | 3 |
| `tests/integration/test_api_endpoints.py` | API integration tests | 20 |
| `tests/load/allocation_load_test.js` | K6 load test script | - |
| `tests/load/seed_dynamodb.py` | DynamoDB seeding for load tests | - |

---

## 🚀 What's Next

### Immediate: Multi-Student Load Test
**Goal**: Verify no double-allocations with multi-student simulation
**Plan**:
1. Seed 200 test sandboxes to production DynamoDB
2. Simulate 50 students across 5 labs (10 students per lab)
3. Verify each student gets unique sandbox
4. Check zero double-allocations
5. Cleanup test data

### Phase 8: CI/CD Pipeline (Next Priority)
**Tasks**:
- GitHub Actions workflow for automated testing
- Docker build and push to ECR on merge
- ECS deployment automation
- Blue/green deployment strategy
- Rollback procedures

**Estimated Effort**: 1-2 days

### Phase 9: GameDay Testing
**Tasks**:
- Chaos engineering scenarios (DynamoDB throttling, ECS failures, CSP API down)
- Load test at 1000+ concurrent requests
- Pool exhaustion verification
- Auto-expiry validation (4.5h timeout)

**Estimated Effort**: 2-3 days

### Phase 10: Production Hardening
**Tasks**:
- CloudWatch dashboards (allocation rate, pool size, error rate)
- Alerting rules (SNS/PagerDuty)
- Operational runbooks
- Performance tuning
- Cost optimization

**Estimated Effort**: 1-2 days

---

## 📖 How to Use the API

### For Instruqt Integration

**1. Allocate Sandbox (Student Starts Lab)**
```bash
curl -X POST https://api-sandbox-broker.highvelocitynetworking.com/v1/allocate \
  -H "Authorization: Bearer <BROKER_API_TOKEN>" \
  -H "X-Instruqt-Sandbox-ID: inst-student1-abc123" \
  -H "X-Instruqt-Track-ID: aws-security-101"

Response:
{
  "sandbox_id": "2012224",
  "name": "sandbox-1",
  "external_id": "af06cbf7-b07c-4c4f-bfa4-bd7dd0e2d4c3",  // Use this to connect to CSP
  "allocated_at": 1728054123,
  "expires_at": 1728070323  // 4 hours later
}
```

**2. Mark for Deletion (Student Stops Lab)**
```bash
curl -X POST https://api-sandbox-broker.highvelocitynetworking.com/v1/sandboxes/2012224/mark-for-deletion \
  -H "Authorization: Bearer <BROKER_API_TOKEN>" \
  -H "X-Instruqt-Sandbox-ID: inst-student1-abc123"

Response:
{
  "sandbox_id": "2012224",
  "status": "pending_deletion",
  "deletion_requested_at": 1728054500
}
```

**Note**: Background cleanup job will delete from CSP within ~5 minutes.

### For Admin Operations

**Get Pool Statistics**
```bash
curl https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/stats \
  -H "Authorization: Bearer <BROKER_ADMIN_TOKEN>"

Response:
{
  "total": 200,
  "available": 150,
  "allocated": 45,
  "pending_deletion": 5
}
```

**Trigger Sync (Pull New Sandboxes from CSP)**
```bash
curl -X POST https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/sync \
  -H "Authorization: Bearer <BROKER_ADMIN_TOKEN>"
```

---

## 🐛 Troubleshooting

### Pool Exhausted (409 Error)
- **Cause**: All sandboxes allocated
- **Check**: `GET /v1/admin/stats` - see available count
- **Fix**: Wait for students to finish, or increase pool size in ENG CSP

### Cleanup Not Happening
- **Check**: CloudWatch logs for `/ecs/sandbox-broker-background-jobs`
- **Verify**: EventBridge scheduler is running every 5 minutes
- **Manual**: `POST /v1/admin/cleanup` to trigger immediately

### Allocation Taking Long
- **Normal**: p95 = 50ms, p99 = 69ms
- **Slow**: Check CloudWatch metrics for ECS CPU/memory usage
- **Scale**: ECS auto-scales from 2-10 tasks based on CPU

### Swagger UI Not Loading
- **Fixed**: CSP headers relaxed for `/v1/docs` endpoints
- **Verify**: https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
- **Fallback**: Use `/v1/openapi.json` with external tool

---

## 📞 Support & Links

- **Production API**: https://api-sandbox-broker.highvelocitynetworking.com/v1
- **Documentation**: https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
- **GitHub**: https://github.com/iracic82/Sandbox-API-Broker
- **AWS Region**: eu-central-1 (Frankfurt)
- **Monitoring**: CloudWatch Logs + Prometheus metrics

---

**Last Updated**: 2025-10-05
**Version**: 1.1.0 (Multi-Student Support)
**Owner**: Igor Racic
**Status**: 🚀 Production Live
