# Deployment Status - Sandbox Broker API
**Date**: 2025-10-04 15:40
**Status**: ✅ **DEPLOYMENT COMPLETE - PRODUCTION LIVE**

## 🎉 Deployment Summary

The Sandbox Broker API is **fully deployed and operational** on AWS ECS Fargate.

### Live Endpoints
- **API URL**: `https://api-sandbox-broker.highvelocitynetworking.com/v1`
- **Swagger Docs**: `https://api-sandbox-broker.highvelocitynetworking.com/v1/docs`
- **Region**: eu-central-1 (Frankfurt)

### Infrastructure: 49/49 Resources Created ✅

All AWS resources successfully deployed:
- ✅ VPC with multi-AZ subnets (2 public, 2 private)
- ✅ Application Load Balancer with HTTPS (ACM certificate)
- ✅ ECS Fargate cluster with 2 running tasks
- ✅ DynamoDB table with 3 Global Secondary Indexes
- ✅ Secrets Manager with 3 API tokens
- ✅ VPC Endpoints (Secrets Manager, DynamoDB)
- ✅ NAT Gateway with Elastic IP
- ✅ Auto-scaling (2-10 tasks, CPU/Memory triggers)
- ✅ CloudWatch Logs
- ✅ EventBridge Schedulers (sync, cleanup, auto-expiry)
- ✅ IAM roles and policies

## Verified Functionality ✅

### Health Checks
```bash
curl https://api-sandbox-broker.highvelocitynetworking.com/healthz
# Response: {"status":"healthy"}
```

### Admin Stats
```bash
curl -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/stats
# Response: {"total":2,"available":1,"allocated":0,"pending_deletion":1,"stale":0,"deletion_failed":0}
```

### Sandbox Allocation
```bash
curl -X POST \
  -H "Authorization: Bearer a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e" \
  -H "X-Track-ID: deployment-test-1" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/allocate
# Response: {"sandbox_id":"2012220","name":"test","external_id":"...","allocated_at":1759585372,"expires_at":1759599772}
```

### Mark for Deletion
```bash
curl -X POST \
  -H "Authorization: Bearer a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e" \
  -H "X-Track-ID: deployment-test-1" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/sandboxes/2012220/mark-for-deletion
# Response: {"sandbox_id":"2012220","status":"pending_deletion","deletion_requested_at":1759585447}
```

### CSP Sync
```bash
curl -X POST \
  -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/sync
# Response: {"status":"completed","synced":2,"marked_stale":0,"duration_ms":397}
```

## Critical Fixes Applied

### 1. DynamoDB GSI Schema Fix
**Problem**: Application queries failed with "Query condition missed key schema element"

**Root Cause**: Terraform defined GSIs with projection keys (GSI1PK, GSI2PK, etc.) but application used actual data attributes (status, allocated_to_track, idempotency_key).

**Solution**:
- Added missing Sort Key (SK) to primary key
- Updated all 3 GSIs to use actual data attributes:
  - **GSI1 (StatusIndex)**: `status` (hash) + `allocated_at` (range)
  - **GSI2 (TrackIndex)**: `allocated_to_track` (hash) + `allocated_at` (range)
  - **GSI3 (IdempotencyIndex)**: `idempotency_key` (hash) + `allocated_at` (range)

**File**: `terraform/dynamodb.tf`

### 2. VPC Endpoint for Secrets Manager
**Problem**: ECS tasks failed with "ResourceInitializationError: unable to pull secrets from asm"

**Root Cause**: ECS tasks in private subnets couldn't reach Secrets Manager API endpoints.

**Solution**:
- Created Interface VPC endpoint for Secrets Manager
- Added security group allowing HTTPS (443) from VPC CIDR
- Enabled private DNS for seamless API calls

**File**: `terraform/vpc_endpoints.tf`

### 3. Elastic IP Quota Increase
**Problem**: Deployment blocked - "AddressLimitExceeded: maximum number of addresses reached"

**Solution**:
- Requested quota increase from 5 to 10 Elastic IPs
- Request ID: `0117cfa2679b4b0d8a0c51023e2d8040Hxa0jvMu`
- Approved within 20 minutes
- Optimized to use single NAT Gateway instead of 2 (cost savings: ~$32/month)

## Authentication Tokens

All tokens stored in `.tokens.txt` (NOT committed to git):

### Track API Token (for Instruqt tracks)
```
BROKER_API_TOKEN=a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e
```

### Admin Token (for admin endpoints)
```
BROKER_ADMIN_TOKEN=083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c
```

### CSP API Token (Infoblox CSP)
```
CSP_API_TOKEN=ccda70ef61cb8ac8962ca5c337e19c51f41eedd98c1a2341ce94bc928d10cc41
```

## Architecture Overview

```
Internet
    │
    v
Application Load Balancer (HTTPS - ACM Certificate)
    │
    ├─────────────┐
    │             │
    v             v
ECS Task 1    ECS Task 2
(AZ-A)        (AZ-B)
    │             │
    └──────┬──────┘
           │
    ┌──────┴──────┐
    │             │
    v             v
DynamoDB     Secrets Manager
(3 GSIs)     (VPC Endpoint)
    │
    v
NAT Gateway ──> Infoblox CSP API
```

### Key Features
- **Multi-AZ Deployment**: 2 availability zones for high availability
- **Private Subnets**: ECS tasks run in private subnets with NAT Gateway for outbound
- **VPC Endpoints**: Private connectivity to AWS services (no internet routing)
- **Auto-scaling**: 2-10 tasks based on CPU (70%) and Memory (80%)
- **HTTPS Only**: ACM certificate with automatic HTTP→HTTPS redirect
- **Pay-per-request**: DynamoDB on-demand pricing for unpredictable workloads

## Cost Estimate

**Monthly Cost (eu-central-1):**
- ECS Fargate (2 tasks, 1vCPU, 2GB): ~$60
- Application Load Balancer: ~$16
- NAT Gateway (1x): ~$32
- DynamoDB (pay-per-request): ~$5-20
- Data Transfer: Variable
- Secrets Manager: ~$1
- VPC Endpoints: ~$7
- **Total: ~$120-135/month**

## Monitoring & Operations

### View Application Logs
```bash
aws logs tail /ecs/sandbox-broker --follow --region eu-central-1 --profile okta-sso
```

### Check ECS Service Health
```bash
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

### Check ALB Target Health
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

### Force New ECS Deployment
```bash
aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker \
  --force-new-deployment \
  --region eu-central-1 \
  --profile okta-sso
```

### Trigger Background Jobs Manually
```bash
# Sync sandboxes from CSP
curl -X POST \
  -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/sync

# Cleanup pending deletion sandboxes
curl -X POST \
  -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/cleanup

# Auto-expire stale allocations
curl -X POST \
  -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/auto-expire
```

### Enable Background Job Schedulers
```bash
# Currently DISABLED by default to avoid unexpected costs
# To enable, set state = "ENABLED" in terraform/eventbridge.tf and run:
terraform apply
```

## Project Files

```
/Users/iracic/PycharmProjects/Sandbox-API-Broker/
├── app/                          # FastAPI application
│   ├── api/                      # API routes
│   ├── core/                     # Config, auth, logging
│   ├── db/                       # DynamoDB client
│   ├── jobs/                     # Background jobs
│   ├── middleware/               # Rate limiting, logging
│   └── models/                   # Pydantic models
├── terraform/                    # Infrastructure as Code
│   ├── main.tf                   # Provider config
│   ├── vpc.tf                    # VPC, subnets, NAT
│   ├── dynamodb.tf               # DynamoDB table + GSIs ✅ FIXED
│   ├── vpc_endpoints.tf          # Secrets Manager endpoint ✅ NEW
│   ├── ecs.tf                    # ECS cluster, tasks
│   ├── alb.tf                    # Load balancer
│   ├── iam.tf                    # IAM roles
│   ├── secrets.tf                # Secrets Manager
│   ├── cloudwatch.tf             # Logs
│   ├── eventbridge.tf            # Background jobs
│   ├── outputs.tf                # Output values
│   ├── variables.tf              # Input variables
│   └── terraform.tfvars          # Variable values
├── Dockerfile                    # Linux/amd64 compatible
├── requirements.txt              # Python dependencies
├── .tokens.txt                   # API tokens (NOT committed)
├── DEPLOYMENT_GUIDE.md           # Full deployment guide
├── DEPLOYMENT_STATUS.md          # This file
└── README.md                     # Project overview
```

## Git Commits

Latest commits:
```
34edf43 - Fix: DynamoDB GSI schema and add VPC endpoint for Secrets Manager
b64ebc2 - Phase 6: AWS Infrastructure & Enhanced Swagger Documentation
```

## Next Steps (Optional)

### Production Hardening
1. **Enable EventBridge Schedulers** - Currently disabled to avoid costs
2. **Set up CloudWatch Alarms** - Alert on high error rates, CPU, memory
3. **Configure Auto-scaling Policies** - Fine-tune based on actual load
4. **Enable X-Ray Tracing** - Distributed tracing for performance insights
5. **Add WAF Rules** - Web Application Firewall for additional security

### Load Testing
```bash
# Test 1000 concurrent allocations
ab -n 1000 -c 100 \
  -H "Authorization: Bearer a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e" \
  -H "X-Track-ID: load-test-1" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/allocate
```

### Disaster Recovery
- DynamoDB: Point-in-time recovery enabled (last 35 days)
- Secrets: Stored in AWS Secrets Manager with automatic rotation support
- Infrastructure: All defined in Terraform (recreate in minutes)

## Troubleshooting

### Issue: ECS Tasks Not Starting
**Check**: Security groups, VPC endpoints, NAT Gateway
```bash
aws ecs describe-tasks \
  --cluster sandbox-broker-cluster \
  --tasks $(aws ecs list-tasks --cluster sandbox-broker-cluster --query 'taskArns[0]' --output text --profile okta-sso --region eu-central-1) \
  --profile okta-sso \
  --region eu-central-1
```

### Issue: 500 Errors from API
**Check**: Application logs for exceptions
```bash
aws logs tail /ecs/sandbox-broker --follow --region eu-central-1 --profile okta-sso
```

### Issue: DynamoDB Throttling
**Solution**: Switch from PAY_PER_REQUEST to PROVISIONED with auto-scaling
```hcl
# In terraform/dynamodb.tf
billing_mode   = "PROVISIONED"
read_capacity  = 5
write_capacity = 5
```

---

## Summary for Future Sessions

**Deployment Complete**: All infrastructure deployed and tested successfully.

**API Endpoint**: `https://api-sandbox-broker.highvelocitynetworking.com/v1`

**Key Achievements**:
- ✅ 49/49 AWS resources created
- ✅ DynamoDB GSI schema fixed and operational
- ✅ VPC endpoints for private AWS service connectivity
- ✅ Full API workflow tested (allocate, mark-for-deletion, sync)
- ✅ HTTPS with ACM certificate
- ✅ Multi-AZ deployment for high availability

**Status**: **PRODUCTION READY** 🚀

---

**Owner**: Igor (iracic@infoblox.com)
**Deployment Date**: 2025-10-04
**Domain**: api-sandbox-broker.highvelocitynetworking.com
**Region**: eu-central-1
**Repository**: https://github.com/iracic82/Sandbox-API-Broker
