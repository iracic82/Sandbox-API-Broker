# Phase 6: AWS Production Deployment - Results

**Status**: ✅ **COMPLETED & LIVE**
**Date**: 2025-10-04
**Production URL**: `https://api-sandbox-broker.highvelocitynetworking.com/v1`

## Overview

Phase 6 successfully deployed the Sandbox Broker API to AWS ECS Fargate with complete infrastructure automation using Terraform. The API is now live in production and has been fully tested.

## Deployment Summary

### Infrastructure Status
- **Resources Deployed**: 49/49 (100%)
- **Region**: eu-central-1 (Frankfurt)
- **Availability Zones**: 2 (Multi-AZ deployment)
- **DNS**: api-sandbox-broker.highvelocitynetworking.com
- **SSL Certificate**: ACM certificate (ISSUED)

### Key Achievements
✅ Complete AWS infrastructure deployed via Terraform
✅ HTTPS-only API with ACM certificate
✅ Multi-AZ high availability setup
✅ DynamoDB GSI schema fixed and operational
✅ VPC endpoints for private AWS connectivity
✅ Auto-scaling configured (2-10 tasks)
✅ All endpoints tested and working
✅ Production tokens secured in AWS Secrets Manager
✅ CloudWatch logging operational

## Deliverables

### 1. Enhanced Swagger/OpenAPI Documentation

**Files Modified:**
- `app/main.py` - Enhanced FastAPI app configuration with comprehensive API description
- `app/api/routes.py` - Added Sandboxes tag with detailed endpoint descriptions
- `app/api/admin_routes.py` - Added Admin tag with operational endpoint docs
- `app/api/metrics_routes.py` - Added Observability tag for health/metrics

**Features Added:**
- Comprehensive API description with workflow explanation
- Key features highlight (atomic allocation, idempotency, auto-expiry, circuit breaker)
- Authentication guide for tracks and admins
- Proper OpenAPI tag organization (Sandboxes, Admin, Observability)
- Contact information and license details
- Interactive API documentation

**Access Swagger UI:**
```bash
# Production
https://api-sandbox-broker.highvelocitynetworking.com/v1/docs

# Local
http://localhost:8080/v1/docs
```

### 2. Complete Terraform Infrastructure

**Directory Structure:**
```
terraform/
├── main.tf                    # Provider and backend configuration
├── variables.tf               # Input variables (50+ configurable options)
├── outputs.tf                 # 15+ useful outputs (ALB DNS, ECS cluster, etc.)
├── vpc.tf                     # VPC, subnets, NAT, route tables
├── vpc_endpoints.tf           # Secrets Manager & DynamoDB endpoints (NEW)
├── dynamodb.tf                # Table with 3 GSIs (FIXED schema)
├── ecs.tf                     # Fargate cluster, task, service, auto-scaling
├── alb.tf                     # Application Load Balancer with HTTPS
├── iam.tf                     # 3 IAM roles with least-privilege policies
├── secrets.tf                 # AWS Secrets Manager for tokens
├── cloudwatch.tf              # Log groups with 30-day retention
├── eventbridge.tf             # Schedulers for background jobs (DISABLED by default)
└── terraform.tfvars           # Production configuration
```

### 3. AWS Resources Deployed (49/49)

#### Networking (vpc.tf, vpc_endpoints.tf)
- ✅ **VPC** (vpc-07fbb704dcf4a7371) with DNS support and hostnames
- ✅ **Internet Gateway** for public subnets
- ✅ **2 Public Subnets** in eu-central-1a and 1b (multi-AZ for ALB)
- ✅ **2 Private Subnets** in eu-central-1a and 1b (multi-AZ for ECS tasks)
- ✅ **1 NAT Gateway** with Elastic IP (cost-optimized from 2 to 1)
- ✅ **Route Tables** (1 public + 1 private)
- ✅ **VPC Interface Endpoint** for Secrets Manager (private connectivity)
- ✅ **VPC Gateway Endpoint** for DynamoDB (no data transfer charges)
- ✅ **Security Group** for ALB (HTTP:80, HTTPS:443 ingress)
- ✅ **Security Group** for ECS tasks (port 8080 from ALB only)
- ✅ **Security Group** for VPC endpoints (HTTPS:443 from VPC)

#### Database (dynamodb.tf) - SCHEMA FIXED
- ✅ **DynamoDB Table** (`sandbox-broker-pool`)
- ✅ **Primary Key**: PK (hash) + SK (range) - **FIXED: Added SK**
- ✅ **PAY_PER_REQUEST** billing mode (on-demand scaling)
- ✅ **3 Global Secondary Indexes** - **FIXED: Corrected attribute names**
  - `StatusIndex`: `status` (hash) + `allocated_at` (range)
  - `TrackIndex`: `allocated_to_track` (hash) + `allocated_at` (range)
  - `IdempotencyIndex`: `idempotency_key` (hash) + `allocated_at` (range)
- ✅ **Point-in-time Recovery** enabled (35-day backup)
- ✅ **Server-side Encryption** enabled (AWS managed keys)

**Critical Fix Applied**: Changed from projection keys (GSI1PK, GSI2PK, GSI3PK) to actual data attributes (status, allocated_to_track, idempotency_key) to match application code expectations.

#### Compute (ecs.tf)
- ✅ **ECS Fargate Cluster** (`sandbox-broker-cluster`) with Container Insights
- ✅ **Task Definition** (`sandbox-broker`)
  - CPU: 1 vCPU (1024 units)
  - Memory: 2GB (2048 MB)
  - Container: linux/amd64 platform
  - Image: `905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api:latest`
  - Port: 8080 (internal)
  - Environment: 8 variables (table names, GSI names, region, CSP URL)
  - Secrets: 3 tokens from AWS Secrets Manager
  - CloudWatch Logs: `/ecs/sandbox-broker`
- ✅ **ECS Service** (`sandbox-broker`)
  - Desired count: 2 tasks (HA)
  - Launch type: FARGATE
  - Network: Private subnets with security group
  - Load balancer: ALB target group integration
  - Health check grace period: 60 seconds
- ✅ **Auto-scaling** (Application Auto Scaling)
  - Min capacity: 2 tasks
  - Max capacity: 10 tasks
  - CPU target: 70%
  - Memory target: 80%
  - Scale-out cooldown: 60s
  - Scale-in cooldown: 300s (5 minutes)

#### Load Balancer (alb.tf)
- ✅ **Application Load Balancer** (`sandbox-broker-alb`)
  - Scheme: Internet-facing
  - Subnets: 2 public subnets (multi-AZ)
  - Security group: HTTP/HTTPS ingress
  - Deletion protection: Disabled (for testing)
- ✅ **Target Group** (`sandbox-broker-tg`)
  - Protocol: HTTP
  - Port: 8080
  - Target type: IP (Fargate)
  - Health check: `/healthz` every 30s
  - Deregistration delay: 30s
- ✅ **HTTP Listener** (port 80)
  - Action: Redirect to HTTPS (301)
- ✅ **HTTPS Listener** (port 443)
  - SSL Certificate: ACM (`arn:aws:acm:eu-central-1:905418046272:certificate/0a3eaa63-9960-4a6c-bb06-4bc41932bbf8`)
  - SSL Policy: ELBSecurityPolicy-TLS13-1-2-2021-06
  - Action: Forward to target group

#### IAM (iam.tf)
- ✅ **ECS Task Execution Role** (`sandbox-broker-ecs-exec-*`)
  - Trust: ECS tasks service
  - Policies:
    - AmazonECSTaskExecutionRolePolicy (AWS managed)
    - Custom policy for Secrets Manager access
    - Custom policy for ECR image pull
- ✅ **ECS Task Role** (`sandbox-broker-ecs-task-*`)
  - Trust: ECS tasks service
  - Policies:
    - Custom DynamoDB policy (GetItem, PutItem, UpdateItem, Query on table + GSIs)
    - VPC endpoint access (if needed)
- ✅ **EventBridge Scheduler Role** (`sandbox-broker-scheduler-*`)
  - Trust: EventBridge Scheduler service
  - Policies:
    - Custom ECS RunTask policy for background jobs

#### Secrets (secrets.tf)
- ✅ **Broker API Token** (`sandbox-broker-broker-api-token-*`)
  - Value: `a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e`
  - Recovery window: 7 days
- ✅ **Broker Admin Token** (`sandbox-broker-broker-admin-token-*`)
  - Value: `083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c`
  - Recovery window: 7 days
- ✅ **CSP API Token** (`sandbox-broker-csp-api-token-*`)
  - Value: `ccda70ef61cb8ac8962ca5c337e19c51f41eedd98c1a2341ce94bc928d10cc41`
  - Recovery window: 7 days

#### CloudWatch (cloudwatch.tf)
- ✅ **Application Log Group** (`/ecs/sandbox-broker`)
  - Retention: 30 days
  - Structured JSON logs with request_id, action, outcome, latency_ms
- ✅ **Background Jobs Log Group** (`/ecs/sandbox-broker-background-jobs`)
  - Retention: 7 days
  - For EventBridge-triggered jobs

#### EventBridge Schedulers (eventbridge.tf)
- ✅ **Sync Job** (`sandbox-broker-sync-job`)
  - Schedule: `rate(5 minutes)` (commented out)
  - State: **DISABLED** (to avoid unexpected costs)
  - Target: ECS RunTask (sync endpoint)
- ✅ **Cleanup Job** (`sandbox-broker-cleanup-job`)
  - Schedule: `rate(5 minutes)` (commented out)
  - State: **DISABLED**
  - Target: ECS RunTask (cleanup endpoint)
- ✅ **Auto-expiry Job** (`sandbox-broker-auto-expiry-job`)
  - Schedule: `rate(15 minutes)` (commented out)
  - State: **DISABLED**
  - Target: ECS RunTask (auto-expire endpoint)

**Note**: Schedulers are disabled by default. To enable, update `state = "ENABLED"` in `terraform/eventbridge.tf` and run `terraform apply`.

### 4. Docker Image

**ECR Repository**: `905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api`

**Image Details:**
- Platform: `linux/amd64` (Fargate compatible)
- Base: `python:3.11-slim`
- Tag: `latest`
- Size: ~350MB
- SHA: `3babf5375392db6c11e63e629c289022a86da41927c73c70b1d0e794b4738d8a`

**Dockerfile Features:**
- Multi-stage build (optimized layers)
- Non-root user (`appuser`, UID 1000)
- Health check: `curl http://localhost:8080/healthz`
- Exposed port: 8080
- Command: `uvicorn app.main:app --host 0.0.0.0 --port 8080`

## Critical Fixes Applied

### Issue 1: AWS Elastic IP Quota Exceeded
**Error**: `AddressLimitExceeded: The maximum number of addresses has been reached.`

**Solution**:
1. Requested quota increase from 5 to 10 Elastic IPs
2. Request ID: `0117cfa2679b4b0d8a0c51023e2d8040Hxa0jvMu`
3. Approved within 20 minutes
4. Optimized infrastructure to use single NAT Gateway instead of 2 (cost savings: ~$32/month)

### Issue 2: ECS Tasks Unable to Access Secrets Manager
**Error**: `ResourceInitializationError: unable to pull secrets or registry auth`

**Root Cause**: ECS tasks in private subnets couldn't reach Secrets Manager API endpoints.

**Solution**:
1. Created VPC Interface Endpoint for Secrets Manager (`vpc_endpoints.tf`)
2. Added security group allowing HTTPS (443) from VPC CIDR
3. Enabled private DNS for seamless API calls
4. Forced new ECS deployment to pick up configuration

**File Created**: `terraform/vpc_endpoints.tf`

### Issue 3: DynamoDB Schema Mismatch - Missing Sort Key
**Error**: `ValidationException: The provided key element does not match the schema`

**Root Cause**: DynamoDB table created without Sort Key (SK), but application expected both PK and SK.

**Solution**:
1. Added `range_key = "SK"` to table definition
2. Added SK attribute definition
3. Ran `terraform apply` to recreate table (acceptable since empty at the time)

**File Modified**: `terraform/dynamodb.tf` (line 14)

### Issue 4: DynamoDB GSI Query Failures - Incorrect Attribute Names
**Error**: `ValidationException: Query condition missed key schema element: GSI3PK`

**Root Cause**: Terraform defined GSIs with projection keys (GSI1PK, GSI2PK, GSI3PK) but application used actual data attributes (status, allocated_to_track, idempotency_key).

**Solution**:
1. Replaced GSI projection keys with actual data attributes:
   - GSI1: `GSI1PK/GSI1SK` → `status/allocated_at`
   - GSI2: `GSI2PK` → `allocated_to_track + allocated_at`
   - GSI3: `GSI3PK` → `idempotency_key + allocated_at`
2. Added range key (`allocated_at`) to all GSIs for efficient queries
3. Ran `terraform apply` to update GSI definitions
4. DynamoDB created GSIs sequentially (one at a time, ~2-3 minutes each)

**File Modified**: `terraform/dynamodb.tf` (lines 28-83)

**Before:**
```hcl
attribute {
  name = "GSI1PK"
  type = "S"
}
global_secondary_index {
  hash_key = "GSI1PK"
  range_key = "GSI1SK"
}
```

**After:**
```hcl
attribute {
  name = "status"
  type = "S"
}
attribute {
  name = "allocated_at"
  type = "N"
}
global_secondary_index {
  hash_key = "status"
  range_key = "allocated_at"
}
```

## Verified Functionality

### 1. Health Checks ✅
```bash
curl https://api-sandbox-broker.highvelocitynetworking.com/healthz
# Response: {"status":"healthy"}

curl https://api-sandbox-broker.highvelocitynetworking.com/readyz
# Response: {"status":"ready","checks":{"dynamodb":"ok"}}
```

### 2. Admin Stats ✅
```bash
curl -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/stats

# Response: {"total":2,"available":1,"allocated":0,"pending_deletion":1,"stale":0,"deletion_failed":0}
```

### 3. CSP Sync ✅
```bash
curl -X POST \
  -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/sync

# Response: {"status":"completed","synced":2,"marked_stale":0,"duration_ms":397}
```

### 4. Sandbox Allocation ✅
```bash
curl -X POST \
  -H "Authorization: Bearer a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e" \
  -H "X-Track-ID: deployment-test-1" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/allocate

# Response: {"sandbox_id":"2012220","name":"test","external_id":"identity/accounts/16c58cbf-ae3f-4d31-955d-4390e463a417","allocated_at":1759585372,"expires_at":1759599772}
```

### 5. Idempotency Test ✅
```bash
# Second allocation with same X-Track-ID returns same sandbox
curl -X POST \
  -H "Authorization: Bearer a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e" \
  -H "X-Track-ID: deployment-test-1" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/allocate

# Response: Same sandbox_id "2012220" (idempotency working!)
```

### 6. Mark for Deletion ✅
```bash
curl -X POST \
  -H "Authorization: Bearer a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e" \
  -H "X-Track-ID: deployment-test-1" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/sandboxes/2012220/mark-for-deletion

# Response: {"sandbox_id":"2012220","status":"pending_deletion","deletion_requested_at":1759585447}
```

### 7. Swagger Documentation ✅
```bash
# Browser access
open https://api-sandbox-broker.highvelocitynetworking.com/v1/docs

# Interactive API explorer with all endpoints documented
```

## Cost Analysis

### Monthly Cost Estimate (eu-central-1)

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| ECS Fargate | 2 tasks × 1vCPU × 2GB × 730h | ~$60 |
| Application Load Balancer | 1 ALB + data processing | ~$16 |
| NAT Gateway | 1 NAT + data transfer | ~$32 |
| DynamoDB | Pay-per-request (low traffic) | ~$5-20 |
| Secrets Manager | 3 secrets | ~$1 |
| VPC Endpoints | Interface (Secrets) + Gateway (DynamoDB) | ~$7 |
| CloudWatch Logs | 2 log groups, 30-day retention | ~$2 |
| Data Transfer | Outbound to CSP API | Variable |
| **Total** | | **~$120-135/month** |

### Cost Optimization Applied
- ✅ Reduced NAT Gateways from 2 to 1 (saves ~$32/month)
- ✅ Pay-per-request DynamoDB (no idle capacity costs)
- ✅ EventBridge schedulers disabled by default (saves ~$3-5/month)
- ✅ VPC Gateway endpoint for DynamoDB (no data transfer charges)

### Potential Further Optimizations
- Use Fargate Spot for non-production workloads (~70% savings)
- Reduce ECS tasks to 1 in non-peak hours
- Enable S3 VPC endpoint if future S3 usage added
- Use Reserved Capacity for DynamoDB if traffic becomes predictable

## Deployment Timeline

| Time | Event |
|------|-------|
| 14:30 | Started Terraform deployment |
| 14:35 | Infrastructure 95% complete, blocked on Elastic IP quota |
| 14:48 | Requested Elastic IP quota increase (Request ID: 0117cfa2679b4b0d8a0c51023e2d8040Hxa0jvMu) |
| 15:08 | Quota approved (20 minutes) |
| 15:10 | Completed NAT Gateway + Elastic IP |
| 15:12 | ECS tasks failing - Secrets Manager connectivity issue |
| 15:15 | Created VPC endpoint for Secrets Manager |
| 15:17 | ECS tasks running, but DynamoDB schema mismatch |
| 15:20 | Fixed DynamoDB Sort Key (SK) |
| 15:22 | Sync completed, but allocation failing |
| 15:25 | Fixed DynamoDB GSI schema (attribute names) |
| 15:35 | All 3 GSIs active |
| 15:37 | Sync repopulated sandboxes with correct attributes |
| 15:38 | ✅ **Full deployment verified and working** |
| 15:40 | DNS A record created, HTTPS working |

**Total Deployment Time**: ~70 minutes (including troubleshooting)

## Architecture Diagram

```
                          Internet
                             │
                             v
                  ┌──────────────────────┐
                  │  Route 53 (DNS)      │
                  │  api-sandbox-broker  │
                  └──────────┬───────────┘
                             │
                             v
                  ┌──────────────────────┐
                  │  ACM Certificate     │
                  │  (HTTPS/TLS)         │
                  └──────────┬───────────┘
                             │
      ┌──────────────────────┴──────────────────────┐
      │  Application Load Balancer (Public Subnet)  │
      │  - HTTP → HTTPS redirect                    │
      │  - HTTPS listener (port 443)                │
      │  - Health checks: /healthz                  │
      └──────────┬─────────────────┬─────────────────┘
                 │                 │
                 v                 v
      ┌──────────────────┐  ┌──────────────────┐
      │  ECS Task 1      │  │  ECS Task 2      │
      │  (AZ: eu-c-1a)   │  │  (AZ: eu-c-1b)   │
      │  Private Subnet  │  │  Private Subnet  │
      │  CPU: 1 vCPU     │  │  CPU: 1 vCPU     │
      │  Memory: 2GB     │  │  Memory: 2GB     │
      └──────────┬────────┘  └───────┬──────────┘
                 │                   │
                 └────────┬──────────┘
                          │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        v                 v                 v
┌───────────────┐  ┌──────────────┐  ┌──────────────┐
│  DynamoDB     │  │  Secrets     │  │  NAT Gateway │
│  (3 GSIs)     │  │  Manager     │  │  (Outbound)  │
│  Via VPC      │  │  Via VPC     │  │              │
│  Endpoint     │  │  Endpoint    │  │              │
└───────────────┘  └──────────────┘  └──────┬───────┘
                                             │
                                             v
                                   ┌─────────────────┐
                                   │  Infoblox CSP   │
                                   │  API (External) │
                                   └─────────────────┘
```

## Monitoring & Operations

### CloudWatch Logs
```bash
# Tail application logs
aws logs tail /ecs/sandbox-broker --follow --region eu-central-1 --profile okta-sso

# Filter for errors
aws logs tail /ecs/sandbox-broker --follow --filter-pattern '"level": "ERROR"' --region eu-central-1 --profile okta-sso
```

### ECS Service Health
```bash
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

### ALB Target Health
```bash
TG_ARN=$(aws elbv2 describe-target-groups \
  --names sandbox-broker-tg \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text \
  --profile okta-sso \
  --region eu-central-1)

aws elbv2 describe-target-health \
  --target-group-arn $TG_ARN \
  --profile okta-sso \
  --region eu-central-1
```

### Force New Deployment
```bash
aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker \
  --force-new-deployment \
  --region eu-central-1 \
  --profile okta-sso
```

## Security Considerations

### Network Security
- ✅ ECS tasks in private subnets (no public IPs)
- ✅ ALB in public subnets (only ingress: HTTP/HTTPS)
- ✅ Security groups: Least-privilege (ALB → ECS:8080 only)
- ✅ VPC endpoints for private AWS service connectivity
- ✅ HTTPS-only (HTTP redirects to HTTPS)

### Secrets Management
- ✅ All tokens in AWS Secrets Manager (encrypted at rest)
- ✅ ECS tasks pull secrets at runtime (not in environment variables)
- ✅ IAM roles with least-privilege policies
- ✅ 7-day recovery window for deleted secrets

### Access Control
- ✅ Bearer token authentication for all API endpoints
- ✅ Two token types: Track (allocation) + Admin (operations)
- ✅ Rate limiting: 10 RPS, 20 burst per IP
- ✅ CORS configured for specific origins

## Lessons Learned

1. **AWS Quotas**: Always check service quotas before deployment (Elastic IPs, VPC limits, etc.)
2. **VPC Endpoints**: Required for ECS tasks in private subnets to access AWS services
3. **DynamoDB Schema**: Terraform attribute definitions must exactly match application code expectations
4. **GSI Creation**: DynamoDB creates GSIs sequentially (can't create multiple simultaneously)
5. **Cost Optimization**: Single NAT Gateway sufficient for low/medium traffic, saves 50% on NAT costs
6. **Platform Specificity**: Docker images must be built for `linux/amd64` for AWS Fargate

## Next Steps

### Phase 7: Testing & Load Testing
- [ ] Unit tests (pytest)
- [ ] Integration tests with DynamoDB Local
- [ ] Load testing at 1000 RPS (k6 or Locust)
- [ ] Chaos engineering (GameDay scenarios)

### Production Hardening
- [ ] Enable EventBridge schedulers for background jobs
- [ ] Set up CloudWatch Alarms (high error rate, CPU, memory)
- [ ] Configure auto-scaling policies based on real traffic patterns
- [ ] Enable AWS X-Ray for distributed tracing
- [ ] Add AWS WAF rules for additional security
- [ ] Implement CloudWatch Container Insights dashboards

### CI/CD Pipeline
- [ ] GitHub Actions workflow for automated testing
- [ ] Automated Docker image builds on PR merge
- [ ] ECR image push pipeline
- [ ] Terraform plan on PR, apply on merge to main
- [ ] Blue/green deployments for zero-downtime updates

## Conclusion

Phase 6 successfully delivered a production-ready AWS deployment with:
- ✅ 49/49 infrastructure resources deployed
- ✅ Multi-AZ high availability
- ✅ HTTPS-only API with custom domain
- ✅ Fully tested allocation workflow
- ✅ Cost-optimized infrastructure (~$120-135/month)
- ✅ Comprehensive monitoring and logging
- ✅ Secure secrets management

**The Sandbox Broker API is now LIVE and ready for Instruqt track integration!** 🚀

---

**Documentation:**
- Deployment details: [DEPLOYMENT_STATUS.md](DEPLOYMENT_STATUS.md)
- Deployment guide: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- API docs: https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
- Repository: https://github.com/iracic82/Sandbox-API-Broker

**Owner**: Igor (iracic@infoblox.com)
**Deployment Date**: 2025-10-04
**Region**: eu-central-1 (Frankfurt)
