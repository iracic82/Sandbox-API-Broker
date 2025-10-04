# Phase 6: AWS Infrastructure & Swagger Documentation - Results

**Status**: ✅ COMPLETED
**Date**: 2025-10-04

## Overview

Phase 6 implements production-grade AWS infrastructure using Terraform and enhances API documentation with comprehensive Swagger/OpenAPI specifications.

## Deliverables

### 1. Enhanced Swagger/OpenAPI Documentation

**Files Modified:**
- `app/main.py` - Enhanced FastAPI app configuration
- `app/api/routes.py` - Added Sandboxes tag
- `app/api/admin_routes.py` - Added Admin tag
- `app/api/metrics_routes.py` - Added Observability tag

**Features Added:**
- Comprehensive API description with workflow explanation
- Key features highlight (atomic allocation, idempotency, auto-expiry, circuit breaker)
- Authentication guide for tracks and admins
- Proper OpenAPI tag organization (Sandboxes, Admin, Observability)
- Contact information and license details
- Interactive API documentation at `/v1/docs`

**Access Swagger UI:**
```bash
http://localhost:8080/v1/docs
```

### 2. Complete Terraform Infrastructure

**Directory Structure:**
```
terraform/
├── main.tf                    # Provider and backend configuration
├── variables.tf               # Input variables (50+ configurable options)
├── outputs.tf                 # 15+ useful outputs
├── vpc.tf                     # VPC, subnets, NAT, security groups
├── dynamodb.tf                # Table with 3 GSIs
├── ecs.tf                     # Fargate cluster, task, service, auto-scaling
├── alb.tf                     # Application Load Balancer with HTTP/HTTPS
├── iam.tf                     # 3 IAM roles with least-privilege policies
├── secrets.tf                 # AWS Secrets Manager for tokens
├── cloudwatch.tf              # Log groups with retention
├── eventbridge.tf             # Schedulers for background jobs
├── terraform.tfvars.example   # Example configuration
└── README.md                  # Comprehensive deployment guide
```

### 3. AWS Resources Provisioned

#### Networking (vpc.tf)
- [x] **VPC** with DNS support
- [x] **Internet Gateway** for public subnets
- [x] **2 Public Subnets** (multi-AZ for ALB)
- [x] **2 Private Subnets** (multi-AZ for ECS tasks)
- [x] **2 NAT Gateways** with Elastic IPs (HA setup)
- [x] **Route Tables** (public + 2 private)
- [x] **VPC Endpoint** for DynamoDB (no data transfer charges)
- [x] **Security Group** for ALB (HTTP/HTTPS ingress)
- [x] **Security Group** for ECS tasks (ALB ingress only)

#### Database (dynamodb.tf)
- [x] **DynamoDB Table** (`sandbox-broker-pool`)
- [x] **PAY_PER_REQUEST** billing mode (on-demand)
- [x] **3 Global Secondary Indexes**:
  - `StatusIndex` (GSI1PK + GSI1SK)
  - `TrackIndex` (GSI2PK)
  - `IdempotencyIndex` (GSI3PK)
- [x] **Point-in-time Recovery** enabled
- [x] **Server-side Encryption** enabled

#### Compute (ecs.tf)
- [x] **ECS Fargate Cluster** with Container Insights
- [x] **Task Definition** (1 vCPU, 2GB RAM)
  - Container: `sandbox-broker-api:latest`
  - Environment: 8 variables (table names, region, CSP URL)
  - Secrets: 3 from Secrets Manager (tokens)
  - Health check: `/healthz` endpoint
  - Logs: CloudWatch
- [x] **ECS Service**
  - Desired count: 2 (HA)
  - Private subnets (no public IP)
  - Rolling updates (200% max, 100% min)
  - Deployment circuit breaker with auto-rollback
- [x] **Auto-scaling** (2-10 tasks)
  - CPU > 70% → scale out
  - Memory > 80% → scale out
  - 5-minute cooldown

#### Load Balancer (alb.tf)
- [x] **Application Load Balancer** (internet-facing)
- [x] **Target Group** (IP type for Fargate)
  - Health check: `/healthz` every 30s
  - Deregistration delay: 30s
- [x] **HTTP Listener** (port 80)
  - Redirect to HTTPS if enabled
  - Forward to target group if HTTP-only
- [x] **HTTPS Listener** (port 443, optional)
  - TLS 1.3 policy
  - ACM certificate required

#### Security (iam.tf + secrets.tf)
- [x] **ECS Task Execution Role**
  - Pull Docker images from ECR
  - Write to CloudWatch Logs
  - Read secrets from Secrets Manager
- [x] **ECS Task Role**
  - DynamoDB full access (table + indexes)
  - Outbound HTTPS for CSP API
- [x] **EventBridge Scheduler Role**
  - Run ECS tasks
  - Pass IAM roles
- [x] **3 Secrets in Secrets Manager**
  - `broker-api-token` (track authentication)
  - `broker-admin-token` (admin endpoints)
  - `csp-api-token` (Infoblox CSP)

#### Observability (cloudwatch.tf)
- [x] **CloudWatch Log Group** (`/ecs/sandbox-broker`)
- [x] **Log Retention**: 30 days (configurable)
- [x] **Structured JSON Logs** from FastAPI

#### Background Jobs (eventbridge.tf)
- [x] **EventBridge Schedule**: Sync job (10 minutes)
- [x] **EventBridge Schedule**: Cleanup job (5 minutes)
- [x] **EventBridge Schedule**: Auto-expiry job (5 minutes)
- [x] **State**: DISABLED (jobs run in-process by default)

### 4. Configuration Options

**Terraform Variables** (50+ options in `variables.tf`):

| Category | Variables | Description |
|----------|-----------|-------------|
| **AWS** | `aws_region`, `environment` | Region and environment name |
| **VPC** | `vpc_cidr`, `availability_zones` | Network configuration |
| **ECS** | `ecs_task_cpu/memory`, `ecs_desired_count`, `ecs_autoscaling_min/max` | Container resources |
| **Container** | `container_image`, `container_port` | Docker image URI |
| **DynamoDB** | `ddb_read_capacity`, `ddb_write_capacity` | Provisioned mode settings |
| **Secrets** | `broker_api_token`, `broker_admin_token`, `csp_api_token` | Authentication tokens |
| **CSP** | `csp_base_url` | Infoblox CSP API endpoint |
| **HTTPS** | `enable_https`, `certificate_arn` | TLS configuration |
| **Monitoring** | `log_retention_days` | CloudWatch retention |
| **Jobs** | `sync_schedule`, `cleanup_schedule`, `auto_expiry_schedule` | Cron expressions |

### 5. Deployment Guide

Created comprehensive `terraform/README.md` covering:

**Quick Start:**
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
export TF_VAR_broker_api_token="your-token"
export TF_VAR_broker_admin_token="your-admin-token"
export TF_VAR_csp_api_token="your-csp-token"
terraform init
terraform plan
terraform apply
```

**Topics Covered:**
- Prerequisites and AWS setup
- Cost estimation (~$150-200/month)
- HTTPS configuration with ACM
- Auto-scaling tuning
- Background job migration to EventBridge
- Monitoring with CloudWatch
- Deployment updates (rolling)
- Secret rotation
- Troubleshooting guide
- Remote state setup (S3 backend)
- Security best practices

### 6. Outputs

**Terraform Outputs** (15 values):

| Output | Description | Example |
|--------|-------------|---------|
| `alb_dns_name` | ALB DNS name | `sandbox-broker-alb-123.us-east-1.elb.amazonaws.com` |
| `alb_url` | Full ALB URL | `http://sandbox-broker-alb-123.us-east-1.elb.amazonaws.com` |
| `api_endpoint` | API base URL | `http://sandbox-broker-alb-123.us-east-1.elb.amazonaws.com/v1` |
| `ecs_cluster_name` | ECS cluster name | `sandbox-broker-cluster` |
| `ecs_service_name` | ECS service name | `sandbox-broker` |
| `dynamodb_table_name` | DynamoDB table name | `sandbox-broker-pool` |
| `cloudwatch_log_group` | Log group name | `/ecs/sandbox-broker` |
| `secrets_*_arn` | Secrets Manager ARNs | 3 secret ARNs |
| `vpc_id` | VPC ID | `vpc-abc123` |
| `private_subnet_ids` | Private subnet IDs | `[subnet-123, subnet-456]` |
| `public_subnet_ids` | Public subnet IDs | `[subnet-789, subnet-abc]` |

## Cost Analysis

**Monthly costs (us-east-1, 2 tasks running 24/7):**

| Resource | Cost | Notes |
|----------|------|-------|
| **ECS Fargate** | ~$60 | 2 tasks × 1 vCPU × 2GB RAM |
| **ALB** | ~$16 | $0.0225/hr + LCU charges |
| **NAT Gateway** | ~$64 | 2 AZs × $0.045/hr × 720hrs |
| **DynamoDB** | ~$5-20 | Pay-per-request (depends on RPS) |
| **Secrets Manager** | ~$1 | 3 secrets × $0.40/month |
| **CloudWatch Logs** | ~$5 | 30-day retention |
| **Data Transfer** | Variable | First 1GB free, then $0.09/GB |

**Total: ~$150-200/month**

**Cost Optimization Tips:**
1. **Single NAT Gateway**: -$32/month (loses HA)
2. **Provisioned DynamoDB**: If steady workload (>50 RPS)
3. **Reduce log retention**: 7 days instead of 30
4. **Spot capacity**: Not available for Fargate
5. **Reserved capacity**: Not applicable

## Testing Checklist

### ✅ Terraform Validation
```bash
cd terraform
terraform init
terraform validate
terraform fmt -check
```

### ✅ Swagger Documentation
- [x] Access http://localhost:8080/v1/docs
- [x] Verify 3 sections: Sandboxes, Admin, Observability
- [x] Check endpoint descriptions
- [x] Test "Try it out" functionality
- [x] Verify authentication requirements shown

### 🔲 AWS Deployment (Manual)
**After running `terraform apply`:**
- [ ] Verify ALB is healthy: `curl http://<alb-dns>/healthz`
- [ ] Check ECS tasks running: `aws ecs list-tasks --cluster sandbox-broker-cluster`
- [ ] Verify logs: `aws logs tail /ecs/sandbox-broker --follow`
- [ ] Test API endpoint: `curl -H "Authorization: Bearer <token>" http://<alb-dns>/v1/allocate`
- [ ] Check DynamoDB table: `aws dynamodb describe-table --table-name sandbox-broker-pool`
- [ ] Verify secrets: `aws secretsmanager list-secrets | grep sandbox-broker`

## Architecture Diagram

```
Internet
    │
    ├─────────────────────────────────────────────┐
    │                                             │
    v                                             v
┌─────────────────────────────────────────────────────┐
│  Application Load Balancer (Multi-AZ)               │
│  - HTTP Listener (Port 80)                          │
│  - HTTPS Listener (Port 443, optional)              │
└───────────────────┬─────────────────────────────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
        v                       v
┌──────────────────┐   ┌──────────────────┐
│   ECS Task 1     │   │   ECS Task 2     │
│   (AZ-A)         │   │   (AZ-B)         │
│                  │   │                  │
│ ┌──────────────┐ │   │ ┌──────────────┐ │
│ │ Sandbox API  │ │   │ │ Sandbox API  │ │
│ │ Container    │ │   │ │ Container    │ │
│ └──────────────┘ │   │ └──────────────┘ │
│   Private Subnet │   │   Private Subnet │
└────────┬─────────┘   └─────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
         v           v           v
   ┌─────────┐  ┌─────────┐  ┌──────────┐
   │DynamoDB │  │ Secrets │  │CloudWatch│
   │  Table  │  │ Manager │  │   Logs   │
   │ + 3 GSI │  │         │  │          │
   └─────────┘  └─────────┘  └──────────┘
         │
         v
   ┌─────────────┐
   │  Infoblox   │
   │  CSP API    │
   └─────────────┘
```

## Infrastructure Features

### High Availability
- ✅ Multi-AZ deployment (2 availability zones)
- ✅ Auto-scaling (2-10 tasks based on CPU/memory)
- ✅ ALB with health checks (30s interval)
- ✅ Rolling updates with circuit breaker
- ✅ NAT Gateways in each AZ

### Security
- ✅ Private subnets for ECS tasks (no public IP)
- ✅ Security groups with least privilege
- ✅ Secrets in AWS Secrets Manager (encrypted)
- ✅ IAM roles with minimal permissions
- ✅ DynamoDB encryption at rest
- ✅ VPC endpoint for DynamoDB (private traffic)
- ✅ HTTPS support with ACM certificates

### Observability
- ✅ CloudWatch Logs with 30-day retention
- ✅ ECS Container Insights
- ✅ Prometheus metrics at `/metrics`
- ✅ Health checks (`/healthz`, `/readyz`)
- ✅ Request tracing with X-Request-ID

### Resilience
- ✅ Deployment circuit breaker (auto-rollback on failure)
- ✅ Auto-scaling on CPU/Memory thresholds
- ✅ Health check grace period (120s)
- ✅ Deregistration delay (30s for in-flight requests)
- ✅ DynamoDB point-in-time recovery

## Migration Path

**Current State**: Local Docker Compose
**Target State**: AWS ECS Fargate

**Migration Steps:**

1. **Build and Push Docker Image**
   ```bash
   docker build -t sandbox-broker-api:v1.0.0 .
   docker tag sandbox-broker-api:v1.0.0 <ecr-repo>:v1.0.0
   docker push <ecr-repo>:v1.0.0
   ```

2. **Configure Terraform Variables**
   ```bash
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   # Edit terraform.tfvars
   ```

3. **Deploy Infrastructure**
   ```bash
   cd terraform
   terraform init
   terraform apply
   ```

4. **Verify Deployment**
   ```bash
   # Get ALB URL
   ALB_URL=$(terraform output -raw alb_url)

   # Test health
   curl $ALB_URL/healthz

   # Test allocation
   curl -X POST $ALB_URL/v1/allocate \
     -H "Authorization: Bearer $TOKEN" \
     -H "X-Track-ID: test-track-1"
   ```

5. **Update Instruqt Tracks**
   - Change API endpoint from CSP to ALB URL
   - Add `X-Track-ID` header
   - Use Broker API token instead of CSP token

## Next Steps

**Phase 7 Recommendations** (if needed):

1. **Production Hardening**
   - [ ] Enable WAF on ALB (protect against attacks)
   - [ ] Add CloudFront CDN (reduce latency)
   - [ ] Enable ALB access logs (debug traffic)
   - [ ] Set up AWS Config (compliance monitoring)
   - [ ] Configure backup strategy (DynamoDB exports)

2. **Monitoring & Alerting**
   - [ ] Create CloudWatch dashboards
   - [ ] Set up SNS alerts for errors
   - [ ] Configure PagerDuty/Opsgenie integration
   - [ ] Add Datadog/New Relic APM (optional)

3. **CI/CD Pipeline**
   - [ ] GitHub Actions workflow
   - [ ] Automated testing (unit + integration)
   - [ ] Docker image build + push to ECR
   - [ ] Blue/green deployments

4. **Documentation**
   - [ ] API usage guide for Instruqt teams
   - [ ] Runbook for on-call engineers
   - [ ] Architecture decision records (ADRs)

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Deployment Time** | < 15 minutes | Terraform apply |
| **API Latency** | < 200ms p99 | CloudWatch metrics |
| **Availability** | 99.9% | ALB metrics |
| **Zero Double-Allocations** | 100% | DynamoDB conditional writes |
| **Auto-scaling** | < 60s | CloudWatch alarms |

## Conclusion

Phase 6 successfully delivers:

1. ✅ **Production-Grade Infrastructure**: Full AWS setup with Terraform
2. ✅ **High Availability**: Multi-AZ, auto-scaling, health checks
3. ✅ **Security**: Secrets Manager, IAM roles, private subnets, encryption
4. ✅ **Observability**: CloudWatch Logs, Container Insights, Prometheus
5. ✅ **Cost-Optimized**: ~$150-200/month with optimization tips
6. ✅ **Comprehensive Documentation**: Terraform README, deployment guide
7. ✅ **Enhanced API Docs**: Swagger/OpenAPI with proper organization

**Ready for Production Deployment!** 🚀

---

**Files Created:**
- `terraform/main.tf` - Provider configuration
- `terraform/variables.tf` - 50+ input variables
- `terraform/outputs.tf` - 15 useful outputs
- `terraform/vpc.tf` - Networking (VPC, subnets, NAT, SG)
- `terraform/dynamodb.tf` - Database with GSIs
- `terraform/ecs.tf` - Fargate cluster, task, service
- `terraform/alb.tf` - Load balancer with HTTP/HTTPS
- `terraform/iam.tf` - IAM roles and policies
- `terraform/secrets.tf` - AWS Secrets Manager
- `terraform/cloudwatch.tf` - Log groups
- `terraform/eventbridge.tf` - Background job schedulers
- `terraform/terraform.tfvars.example` - Configuration example
- `terraform/README.md` - Deployment guide (250+ lines)

**Files Modified:**
- `app/main.py` - Enhanced Swagger documentation
- `app/api/routes.py` - Added Sandboxes tag
- `app/api/admin_routes.py` - Added Admin tag
- `app/api/metrics_routes.py` - Added Observability tag
