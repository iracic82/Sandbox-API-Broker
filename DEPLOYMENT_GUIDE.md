# AWS Deployment Guide
## Domain: api-sandbox-broker.highvelocitynetworking.com

This guide walks through deploying the Sandbox Broker API to AWS ECS Fargate with HTTPS.

## Prerequisites Checklist

- [x] AWS Account with appropriate permissions
- [x] AWS CLI configured (`aws configure`)
- [x] Terraform installed (`terraform --version`)
- [x] Docker installed
- [x] Domain DNS control (highvelocitynetworking.com)
- [ ] ECR repository created
- [ ] ACM certificate created and validated

## Step 1: Create ECR Repository

```bash
# Set your AWS region
export AWS_REGION=us-east-1

# Create ECR repository
aws ecr create-repository \
  --repository-name sandbox-broker-api \
  --region $AWS_REGION

# Output will show repository URI like:
# 123456789012.dkr.ecr.us-east-1.amazonaws.com/sandbox-broker-api
```

**Save the repository URI** - you'll need it for Terraform configuration.

## Step 2: Request ACM Certificate

```bash
# Request certificate for your custom domain
aws acm request-certificate \
  --domain-name api-sandbox-broker.highvelocitynetworking.com \
  --validation-method DNS \
  --region $AWS_REGION

# Output will show certificate ARN like:
# arn:aws:acm:us-east-1:123456789012:certificate/12345678-1234-1234-1234-123456789012
```

**Save the certificate ARN** - you'll need it for Terraform.

## Step 3: Validate ACM Certificate via DNS

```bash
# Get DNS validation records
aws acm describe-certificate \
  --certificate-arn <your-certificate-arn> \
  --region $AWS_REGION \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord' \
  --output table
```

**Output will show:**
```
----------------------------------------------------
|              ResourceRecord                       |
+--------+------------------------------------------+
|  Name  | _abc123.api-sandbox-broker.highvelocity...  |
|  Type  | CNAME                                     |
|  Value | _xyz789.acm-validations.aws.              |
+--------+------------------------------------------+
```

**Action Required:**
1. Log into your DNS provider for `highvelocitynetworking.com`
2. Create a **CNAME record** with the Name and Value from above
3. Wait for DNS propagation (usually 5-10 minutes)

**Verify validation status:**
```bash
aws acm describe-certificate \
  --certificate-arn <your-certificate-arn> \
  --region $AWS_REGION \
  --query 'Certificate.Status' \
  --output text

# Wait until output shows: ISSUED
```

## Step 4: Generate Secure Tokens

```bash
# Generate secure random tokens
export BROKER_API_TOKEN=$(openssl rand -hex 32)
export BROKER_ADMIN_TOKEN=$(openssl rand -hex 32)

# Use your existing CSP token
export CSP_API_TOKEN="your-infoblox-csp-token-here"

# Display tokens (save these securely!)
echo "BROKER_API_TOKEN=$BROKER_API_TOKEN"
echo "BROKER_ADMIN_TOKEN=$BROKER_ADMIN_TOKEN"
echo "CSP_API_TOKEN=$CSP_API_TOKEN"
```

**⚠️ IMPORTANT**: Save these tokens securely! You'll need them to call the API.

## Step 5: Build and Push Docker Image

```bash
# Get ECR login credentials
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  <your-account-id>.dkr.ecr.$AWS_REGION.amazonaws.com

# Build Docker image
docker build -t sandbox-broker-api:latest .

# Tag for ECR
docker tag sandbox-broker-api:latest \
  <your-account-id>.dkr.ecr.$AWS_REGION.amazonaws.com/sandbox-broker-api:latest

# Push to ECR
docker push <your-account-id>.dkr.ecr.$AWS_REGION.amazonaws.com/sandbox-broker-api:latest
```

## Step 6: Configure Terraform Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

**Edit `terraform.tfvars`:**

```hcl
# AWS Configuration
aws_region  = "us-east-1"
environment = "prod"
app_name    = "sandbox-broker"

# VPC Configuration (use defaults or customize)
vpc_cidr           = "10.0.0.0/16"
availability_zones = ["us-east-1a", "us-east-1b"]

# ECS Configuration
ecs_task_cpu        = 1024  # 1 vCPU
ecs_task_memory     = 2048  # 2GB RAM
ecs_desired_count   = 2     # Start with 2 tasks
ecs_autoscaling_min = 2     # Minimum (HA)
ecs_autoscaling_max = 10    # Maximum for peak load

# Container Configuration
container_image = "<your-account-id>.dkr.ecr.us-east-1.amazonaws.com/sandbox-broker-api:latest"
container_port  = 8080

# Application Configuration (use environment variables instead of hardcoding)
# These will be read from TF_VAR_* environment variables
# broker_api_token   = "..." (set via TF_VAR_broker_api_token)
# broker_admin_token = "..." (set via TF_VAR_broker_admin_token)
# csp_api_token      = "..." (set via TF_VAR_csp_api_token)

csp_base_url = "https://csp.infoblox.com/v2"

# HTTPS Configuration
enable_https    = true
certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/12345678-..." # FROM STEP 2

# Monitoring
log_retention_days = 30

# Background Jobs Schedule
sync_schedule        = "rate(10 minutes)"
cleanup_schedule     = "rate(5 minutes)"
auto_expiry_schedule = "rate(5 minutes)"
```

**Set tokens via environment variables (more secure):**
```bash
export TF_VAR_broker_api_token="$BROKER_API_TOKEN"
export TF_VAR_broker_admin_token="$BROKER_ADMIN_TOKEN"
export TF_VAR_csp_api_token="$CSP_API_TOKEN"
```

## Step 7: Deploy Infrastructure with Terraform

```bash
# Initialize Terraform
terraform init

# Validate configuration
terraform validate

# Plan deployment (review what will be created)
terraform plan

# Review the plan carefully, then apply
terraform apply

# Type 'yes' when prompted
```

**Expected resources to be created:**
- VPC with subnets, NAT gateways, security groups
- DynamoDB table with 3 GSIs
- ECS Fargate cluster and service (2 tasks)
- Application Load Balancer
- Secrets Manager (3 secrets)
- CloudWatch log groups
- IAM roles and policies
- EventBridge schedulers

**Deployment time**: ~10-15 minutes

## Step 8: Get ALB DNS Name

```bash
# Get ALB DNS name
terraform output alb_dns_name

# Output: sandbox-broker-alb-1234567890.us-east-1.elb.amazonaws.com
```

## Step 9: Create DNS A Record (ALIAS)

**In your DNS provider for highvelocitynetworking.com:**

Create an **A record** (or ALIAS/CNAME depending on your DNS provider):

```
Type: A (or ALIAS)
Name: api-sandbox-broker.highvelocitynetworking.com
Value: <alb-dns-name-from-step-8>
TTL: 300 (5 minutes)
```

**If your DNS provider supports ALIAS records** (like Route53):
```bash
# If using Route53, you can automate this
aws route53 change-resource-record-sets \
  --hosted-zone-id <your-zone-id> \
  --change-batch '{
    "Changes": [{
      "Action": "CREATE",
      "ResourceRecordSet": {
        "Name": "api-sandbox-broker.highvelocitynetworking.com",
        "Type": "A",
        "AliasTarget": {
          "HostedZoneId": "<alb-zone-id>",
          "DNSName": "<alb-dns-name>",
          "EvaluateTargetHealth": true
        }
      }
    }]
  }'
```

**If ALIAS not supported, use CNAME:**
```
Type: CNAME
Name: api-sandbox-broker
Value: <alb-dns-name>
```

## Step 10: Verify Deployment

### Check ECS Service Health

```bash
# Check ECS service status
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region $AWS_REGION \
  --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount}'

# Expected: Status=ACTIVE, Running=2, Desired=2
```

### Check Task Health

```bash
# List running tasks
aws ecs list-tasks \
  --cluster sandbox-broker-cluster \
  --service-name sandbox-broker \
  --region $AWS_REGION

# Check task details
aws ecs describe-tasks \
  --cluster sandbox-broker-cluster \
  --tasks <task-arn> \
  --region $AWS_REGION
```

### Test Health Endpoint (via ALB directly first)

```bash
# Get ALB URL
ALB_URL=$(terraform output -raw alb_dns_name)

# Test HTTP health endpoint (should redirect to HTTPS)
curl -v http://$ALB_URL/healthz

# Test HTTPS health endpoint
curl https://$ALB_URL/healthz
# Expected: {"status":"healthy","timestamp":1234567890}

# Test readiness
curl https://$ALB_URL/readyz
# Expected: {"status":"ready","checks":{"dynamodb":"ok"}}
```

### Test Custom Domain (wait for DNS propagation)

```bash
# Wait 5-10 minutes for DNS propagation, then test
curl https://api-sandbox-broker.highvelocitynetworking.com/healthz
# Expected: {"status":"healthy","timestamp":1234567890}

# Test Swagger UI
open https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
```

### Test API Endpoints

```bash
# Get stats (admin endpoint)
curl -X GET https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/stats \
  -H "Authorization: Bearer $BROKER_ADMIN_TOKEN" \
  | jq

# Expected: {"total":0,"available":0,"allocated":0,...}

# Trigger sync to populate pool
curl -X POST https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/sync \
  -H "Authorization: Bearer $BROKER_ADMIN_TOKEN" \
  | jq

# Expected: {"status":"completed","synced":3,"marked_stale":0,...}

# Check stats again
curl -X GET https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/stats \
  -H "Authorization: Bearer $BROKER_ADMIN_TOKEN" \
  | jq

# Expected: {"total":3,"available":3,"allocated":0,...}

# Allocate a sandbox (track endpoint)
curl -X POST https://api-sandbox-broker.highvelocitynetworking.com/v1/allocate \
  -H "Authorization: Bearer $BROKER_API_TOKEN" \
  -H "X-Track-ID: test-track-deployment-1" \
  | jq

# Expected: {"sandbox_id":"...", "name":"...", "external_id":"...", "allocated_at":..., "expires_at":...}
```

## Step 11: Monitor Logs

```bash
# View application logs
aws logs tail /ecs/sandbox-broker --follow --region $AWS_REGION

# Filter for errors
aws logs tail /ecs/sandbox-broker --follow --filter-pattern "ERROR" --region $AWS_REGION

# View background job logs
aws logs tail /ecs/sandbox-broker-background-jobs --follow --region $AWS_REGION
```

## Step 12: Access Prometheus Metrics

```bash
# View metrics
curl https://api-sandbox-broker.highvelocitynetworking.com/metrics

# Expected: Prometheus exposition format with metrics like:
# broker_pool_total 3
# broker_pool_available 2
# broker_pool_allocated 1
```

## Post-Deployment Checklist

- [ ] Health check passing: `/healthz` returns HTTP 200
- [ ] Readiness check passing: `/readyz` returns HTTP 200
- [ ] HTTPS working with valid certificate
- [ ] Custom domain resolving correctly
- [ ] Admin sync populates sandboxes
- [ ] Track can allocate sandbox
- [ ] Track can mark sandbox for deletion
- [ ] Cleanup job runs successfully
- [ ] CloudWatch logs streaming
- [ ] Prometheus metrics accessible
- [ ] ECS tasks running (2/2 desired)
- [ ] Auto-scaling configured

## Troubleshooting

### Issue: ECS Tasks Not Starting

**Check task logs:**
```bash
aws logs tail /ecs/sandbox-broker --since 10m --region $AWS_REGION
```

**Common causes:**
- Invalid secrets in Secrets Manager
- DynamoDB table not accessible
- Container image not found in ECR
- IAM role missing permissions

### Issue: Health Checks Failing

**Check ALB target group health:**
```bash
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn> \
  --region $AWS_REGION
```

**Common causes:**
- Security group blocking traffic
- Container not listening on port 8080
- Health check path incorrect
- DynamoDB connection failing

### Issue: Certificate Not Validating

**Check certificate status:**
```bash
aws acm describe-certificate \
  --certificate-arn <certificate-arn> \
  --region $AWS_REGION
```

**Common causes:**
- DNS validation record not created
- DNS propagation not complete (wait 10-30 minutes)
- Wrong DNS record type (must be CNAME)

### Issue: 502 Bad Gateway

**Common causes:**
- ECS tasks not healthy (check `/healthz`)
- Security group blocking ALB → ECS traffic
- Container crashed (check logs)

### Issue: DNS Not Resolving

**Check DNS propagation:**
```bash
dig api-sandbox-broker.highvelocitynetworking.com
nslookup api-sandbox-broker.highvelocitynetworking.com
```

**Common causes:**
- DNS record not created
- TTL not expired (wait)
- Wrong record type (use A or ALIAS, not CNAME for apex)

## Rolling Updates

To deploy a new version:

```bash
# Build and push new image
docker build -t sandbox-broker-api:v2 .
docker tag sandbox-broker-api:v2 <ecr-repo>:v2
docker push <ecr-repo>:v2

# Update terraform.tfvars
container_image = "<ecr-repo>:v2"

# Apply changes (ECS will perform rolling update)
terraform apply

# Monitor deployment
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region $AWS_REGION \
  --query 'services[0].deployments'
```

## Cleanup (Destroy Infrastructure)

**⚠️ WARNING: This will delete ALL resources and data!**

```bash
cd terraform
terraform destroy

# Type 'yes' when prompted
```

## Cost Monitoring

**View estimated monthly costs:**
```bash
aws ce get-cost-and-usage \
  --time-period Start=2025-10-01,End=2025-10-31 \
  --granularity MONTHLY \
  --metrics "UnblendedCost" \
  --group-by Type=DIMENSION,Key=SERVICE
```

**Expected monthly cost:** ~$150-200

## Security Best Practices

1. ✅ Tokens stored in Secrets Manager (encrypted)
2. ✅ ECS tasks in private subnets (no public IP)
3. ✅ HTTPS enabled with ACM certificate
4. ✅ Security groups with least privilege
5. ✅ IAM roles with minimal permissions
6. ✅ DynamoDB encryption at rest
7. ⚠️ Consider: Enable VPC Flow Logs
8. ⚠️ Consider: Enable CloudTrail for audit logging
9. ⚠️ Consider: Enable WAF on ALB

## Next Steps

After successful deployment:

1. **Update Instruqt Tracks**
   - Change API endpoint to: `https://api-sandbox-broker.highvelocitynetworking.com/v1`
   - Add `X-Track-ID` header with track identifier
   - Use `$BROKER_API_TOKEN` for authentication

2. **Set Up Monitoring**
   - Create CloudWatch dashboards
   - Configure SNS alerts for errors
   - Set up PagerDuty/Opsgenie

3. **Load Testing**
   - Run load tests to verify 1000 RPS capacity
   - Monitor auto-scaling behavior
   - Tune ECS task count and DynamoDB capacity

4. **Documentation**
   - Share API documentation with Instruqt teams
   - Create runbook for on-call engineers

---

**Deployment Owner**: Igor
**Deployment Date**: 2025-10-04
**Domain**: api-sandbox-broker.highvelocitynetworking.com
**Repository**: https://github.com/iracic82/Sandbox-API-Broker
