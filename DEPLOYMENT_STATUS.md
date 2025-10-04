# Deployment Status - Sandbox Broker API
**Date**: 2025-10-04 14:50
**Status**: ⏳ WAITING FOR AWS ELASTIC IP QUOTA INCREASE

## Current Situation

Deployment to AWS ECS Fargate is **95% complete** but blocked waiting for AWS to approve an Elastic IP quota increase (usually 10-30 minutes).

### Quota Increase Request Details
- **Request ID**: `0117cfa2679b4b0d8a0c51023e2d8040Hxa0jvMu`
- **Status**: PENDING
- **Current Limit**: 5 Elastic IPs
- **Requested**: 10 Elastic IPs
- **Service**: EC2-VPC Elastic IPs (eu-central-1)
- **Requested At**: 2025-10-04 14:48:16

**Check Status:**
```bash
aws service-quotas get-requested-service-quota-change \
  --request-id 0117cfa2679b4b0d8a0c51023e2d8040Hxa0jvMu \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'RequestedQuota.Status' \
  --output text
```

Expected statuses: `PENDING` → `CASE_OPENED` → `APPROVED`

## What's Been Completed ✅

### 1. AWS Account Setup
- ✅ Logged in via okta-sso
- ✅ Account: 905418046272
- ✅ Region: **eu-central-1**
- ✅ User: iracic

### 2. ACM Certificate (HTTPS)
- ✅ Created certificate for: `api-sandbox-broker.highvelocitynetworking.com`
- ✅ Certificate ARN: `arn:aws:acm:eu-central-1:905418046272:certificate/0a3eaa63-9960-4a6c-bb06-4bc41932bbf8`
- ✅ Status: **ISSUED** (DNS validation complete)

### 3. ECR Repository
- ✅ Repository created: `sandbox-broker-api`
- ✅ Repository URI: `905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api`
- ✅ Docker image built for linux/amd64 (AWS Fargate compatible)
- ✅ Image pushed: `latest` (SHA: 3babf5375392db6c11e63e629c289022a86da41927c73c70b1d0e794b4738d8a)

### 4. Terraform Configuration
- ✅ All Terraform files created in `terraform/` directory
- ✅ Variables configured in `terraform/terraform.tfvars`
- ✅ Terraform initialized
- ✅ Plan created (49 resources to create)

### 5. API Authentication Tokens
- ✅ Secure tokens generated and saved in `.tokens.txt`
- **BROKER_API_TOKEN**: `a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e`
- **BROKER_ADMIN_TOKEN**: `083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c`
- **CSP_API_TOKEN**: `ccda70ef61cb8ac8962ca5c337e19c51f41eedd98c1a2341ce94bc928d10cc41`

### 6. AWS Infrastructure (47/49 Resources Created)

**Successfully Created:**
- ✅ VPC (vpc-07fbb704dcf4a7371)
- ✅ Internet Gateway
- ✅ 2 Public Subnets (multi-AZ)
- ✅ 2 Private Subnets (multi-AZ)
- ✅ Public Route Table
- ✅ Private Route Table
- ✅ Security Groups (ALB + ECS)
- ✅ Application Load Balancer (sandbox-broker-alb)
- ✅ ALB Target Group
- ✅ HTTP Listener (port 80)
- ✅ HTTPS Listener (port 443) with ACM certificate
- ✅ DynamoDB Table: `sandbox-broker-pool` with 3 GSIs
- ✅ ECS Cluster: `sandbox-broker-cluster`
- ✅ ECS Task Definition: `sandbox-broker`
- ✅ ECS Service: `sandbox-broker` (desired: 2 tasks)
- ✅ Auto-scaling Target (2-10 tasks)
- ✅ Auto-scaling Policies (CPU + Memory)
- ✅ CloudWatch Log Groups: `/ecs/sandbox-broker`
- ✅ Secrets Manager (3 secrets with tokens)
- ✅ IAM Roles: ECS Task, ECS Execution, EventBridge
- ✅ IAM Policies (DynamoDB, Secrets, ECS)
- ✅ EventBridge Schedulers (sync, cleanup, auto-expiry) - DISABLED by default
- ✅ VPC Endpoint for DynamoDB

**Blocked (2/49 Resources):**
- ❌ Elastic IP for NAT Gateway (quota limit reached)
- ❌ NAT Gateway (depends on Elastic IP)

**Why This Matters:**
Without NAT Gateway, ECS tasks in private subnets can't reach the internet (needed for pulling Docker images and calling Infoblox CSP API). Everything else is ready!

## Next Steps to Complete Deployment

### Step 1: Wait for Quota Approval (Auto-check)

Once quota is approved (status becomes `APPROVED` or `CASE_OPENED`), run:

```bash
cd /Users/iracic/PycharmProjects/Sandbox-API-Broker

# Set environment variables
export TF_VAR_broker_api_token="a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e"
export TF_VAR_broker_admin_token="083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c"
export TF_VAR_csp_api_token="ccda70ef61cb8ac8962ca5c337e19c51f41eedd98c1a2341ce94bc928d10cc41"
export AWS_PROFILE=okta-sso

# Apply remaining resources
terraform apply

# Should complete in ~2 minutes (just EIP + NAT Gateway)
```

### Step 2: Get ALB DNS Name

```bash
terraform output alb_dns_name
# Example: sandbox-broker-alb-97670aaf85194d2c.eu-central-1.elb.amazonaws.com
```

### Step 3: Create DNS Record

In your DNS provider for `highvelocitynetworking.com`, create:

```
Type: A (or ALIAS)
Name: api-sandbox-broker.highvelocitynetworking.com
Value: <alb-dns-name-from-step-2>
TTL: 300
```

**Or use AWS CLI if using Route53:**
```bash
ALB_DNS=$(terraform output -raw alb_dns_name)
ALB_ZONE_ID=$(aws elbv2 describe-load-balancers \
  --names sandbox-broker-alb \
  --query 'LoadBalancers[0].CanonicalHostedZoneId' \
  --output text \
  --profile okta-sso \
  --region eu-central-1)

# Create Route53 record (if using Route53)
aws route53 change-resource-record-sets \
  --hosted-zone-id <YOUR_ZONE_ID> \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api-sandbox-broker.highvelocitynetworking.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "'$ALB_ZONE_ID'",
          "DNSName": "'$ALB_DNS'",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }' \
  --profile okta-sso
```

### Step 4: Verify Deployment

```bash
# Wait 2-3 minutes for ECS tasks to start, then test:

# Test health endpoint
curl https://api-sandbox-broker.highvelocitynetworking.com/healthz

# Test admin stats (should show 0 sandboxes initially)
curl -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/stats

# Trigger sync to populate sandbox pool
curl -X POST \
  -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/sync

# Check stats again (should show sandboxes from CSP)
curl -H "Authorization: Bearer 083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/stats

# Allocate a test sandbox
curl -X POST \
  -H "Authorization: Bearer a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e" \
  -H "X-Track-ID: deployment-test-1" \
  https://api-sandbox-broker.highvelocitynetworking.com/v1/allocate

# View Swagger docs
open https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
```

## Monitoring & Troubleshooting

### Check ECS Task Status
```bash
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'
```

### View Application Logs
```bash
aws logs tail /ecs/sandbox-broker --follow --region eu-central-1 --profile okta-sso
```

### Check ALB Target Health
```bash
# Get target group ARN
TG_ARN=$(aws elbv2 describe-target-groups \
  --names sandbox-broker-tg \
  --query 'TargetGroups[0].TargetGroupArn' \
  --output text \
  --profile okta-sso \
  --region eu-central-1)

# Check target health
aws elbv2 describe-target-health \
  --target-group-arn $TG_ARN \
  --profile okta-sso \
  --region eu-central-1
```

## Important Files & Locations

```
/Users/iracic/PycharmProjects/Sandbox-API-Broker/
├── .tokens.txt                    # API tokens (DO NOT COMMIT)
├── terraform/
│   ├── terraform.tfvars           # Terraform variables
│   ├── main.tf                    # Provider config
│   ├── vpc.tf                     # VPC, subnets, NAT
│   ├── dynamodb.tf                # DynamoDB table
│   ├── ecs.tf                     # ECS cluster, tasks
│   ├── alb.tf                     # Load balancer
│   ├── iam.tf                     # IAM roles
│   ├── secrets.tf                 # Secrets Manager
│   ├── cloudwatch.tf              # Logs
│   ├── eventbridge.tf             # Background jobs
│   └── outputs.tf                 # Output values
├── Dockerfile                     # Linux/amd64 compatible
├── DEPLOYMENT_GUIDE.md            # Full deployment guide
├── DEPLOYMENT_STATUS.md           # This file
└── PHASE6_RESULTS.md              # Phase 6 results
```

## Architecture Overview

```
Internet
    │
    v
Application Load Balancer (HTTPS)
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
(3 GSIs)     (3 secrets)
    │
    v
Infoblox CSP API
```

## Cost Estimate

**Monthly Cost (eu-central-1):**
- ECS Fargate (2 tasks, 1vCPU, 2GB): ~$60
- Application Load Balancer: ~$16
- NAT Gateway (1x): ~$32
- DynamoDB (pay-per-request): ~$5-20
- Data Transfer: Variable
- Secrets Manager: ~$1
- **Total: ~$115-130/month**

(Saved $32/month by using single NAT Gateway instead of 2)

## Git Commits

Latest commit:
```
b64ebc2 - Phase 6: AWS Infrastructure & Enhanced Swagger Documentation
```

All Phase 6 Terraform files committed and pushed to GitHub.

## Quick Recovery Commands

If session breaks, resume with:

```bash
cd /Users/iracic/PycharmProjects/Sandbox-API-Broker

# Login to AWS
aws sso login --profile okta-sso

# Check quota status
aws service-quotas get-requested-service-quota-change \
  --request-id 0117cfa2679b4b0d8a0c51023e2d8040Hxa0jvMu \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'RequestedQuota.Status'

# If APPROVED, complete deployment
export TF_VAR_broker_api_token="a59dd8c5c9bdf78c36e04253dc5ceab22d1deb3413fca7bd90d4fc485ba4162e"
export TF_VAR_broker_admin_token="083b8da9d39eb2e23a2c80cc27b9a4f650703fb521bb43ffdb55bbb6f547d51c"
export TF_VAR_csp_api_token="ccda70ef61cb8ac8962ca5c337e19c51f41eedd98c1a2341ce94bc928d10cc41"
export AWS_PROFILE=okta-sso
terraform apply
```

## Summary for New Session

**What to tell Claude:**
> "We were deploying the Sandbox Broker API to AWS ECS Fargate in eu-central-1. Deployment is 95% complete (47/49 resources created) but blocked waiting for AWS to approve an Elastic IP quota increase (Request ID: 0117cfa2679b4b0d8a0c51023e2d8040Hxa0jvMu). Once approved, we need to run `terraform apply` to create the remaining 2 resources (Elastic IP + NAT Gateway), then create a DNS A record pointing api-sandbox-broker.highvelocitynetworking.com to the ALB. All details are in DEPLOYMENT_STATUS.md."

---

**Owner**: Igor (iracic@infoblox.com)
**Deployment Date**: 2025-10-04
**Domain**: api-sandbox-broker.highvelocitynetworking.com
**Region**: eu-central-1
**Repository**: https://github.com/iracic82/Sandbox-API-Broker
