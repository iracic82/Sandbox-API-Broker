# Terraform Infrastructure for Sandbox Broker API

This directory contains Terraform configuration for deploying the Sandbox Broker API to AWS ECS Fargate.

## Architecture

- **VPC**: Multi-AZ VPC with public and private subnets
- **ECS Fargate**: Serverless container orchestration
- **Application Load Balancer**: HTTP/HTTPS traffic distribution
- **DynamoDB**: Sandbox pool database with GSIs
- **Secrets Manager**: Secure token storage
- **CloudWatch**: Centralized logging
- **EventBridge Scheduler**: Background job scheduling (optional)

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **Terraform** >= 1.0 installed
3. **AWS CLI** configured with credentials
4. **Docker image** pushed to ECR or Docker Hub
5. **ACM Certificate** (optional, for HTTPS)

## Quick Start

### 1. Configure Variables

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` with your values:

```hcl
aws_region  = "us-east-1"
environment = "prod"

# Container image URI (ECR or Docker Hub)
container_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/sandbox-broker-api:latest"

# Secrets (use environment variables for sensitive data)
broker_api_token   = "your-secure-api-token"
broker_admin_token = "your-secure-admin-token"
csp_api_token      = "your-infoblox-csp-token"
```

**Better approach for secrets:**
```bash
export TF_VAR_broker_api_token="your-token"
export TF_VAR_broker_admin_token="your-admin-token"
export TF_VAR_csp_api_token="your-csp-token"
```

### 2. Initialize Terraform

```bash
terraform init
```

### 3. Review Plan

```bash
terraform plan
```

### 4. Deploy Infrastructure

```bash
terraform apply
```

### 5. Get Outputs

```bash
terraform output alb_dns_name
terraform output api_endpoint
```

## Cost Estimation

**Monthly costs (us-east-1, 2 tasks):**

- **ECS Fargate**: ~$60 (2 tasks × 1vCPU × 2GB RAM)
- **Application Load Balancer**: ~$16
- **NAT Gateway**: ~$64 (2 AZs × $0.045/hr)
- **DynamoDB**: Pay-per-request (~$1-10 depending on usage)
- **Data Transfer**: Variable
- **CloudWatch Logs**: ~$5 (30-day retention)

**Total: ~$150-200/month**

**Cost optimization:**
- Use single NAT Gateway (not HA): -$32/month
- Use DynamoDB provisioned capacity for predictable workloads
- Enable ALB access logs only when debugging

## Files

| File | Description |
|------|-------------|
| `main.tf` | Provider and backend configuration |
| `variables.tf` | Input variables |
| `outputs.tf` | Output values |
| `vpc.tf` | VPC, subnets, security groups |
| `dynamodb.tf` | DynamoDB table with GSIs |
| `ecs.tf` | ECS cluster, task definition, service |
| `alb.tf` | Application Load Balancer |
| `iam.tf` | IAM roles and policies |
| `secrets.tf` | AWS Secrets Manager |
| `cloudwatch.tf` | Log groups |
| `eventbridge.tf` | Background job schedulers (disabled by default) |

## Configuration Options

### HTTPS (Production)

1. Create ACM certificate:
```bash
aws acm request-certificate \
  --domain-name api.yourdomain.com \
  --validation-method DNS
```

2. Enable HTTPS in `terraform.tfvars`:
```hcl
enable_https    = true
certificate_arn = "arn:aws:acm:us-east-1:123456789012:certificate/..."
```

3. Create Route53 alias record:
```hcl
# Add to your DNS configuration
resource "aws_route53_record" "api" {
  zone_id = "YOUR_ZONE_ID"
  name    = "api.yourdomain.com"
  type    = "A"

  alias {
    name                   = aws_lb.main.dns_name
    zone_id                = aws_lb.main.zone_id
    evaluate_target_health = true
  }
}
```

### Auto-scaling

Adjust scaling parameters in `terraform.tfvars`:

```hcl
ecs_desired_count   = 2    # Starting count
ecs_autoscaling_min = 2    # Minimum (HA)
ecs_autoscaling_max = 10   # Maximum (handle spikes)
```

Auto-scaling triggers:
- CPU > 70% → scale out
- Memory > 80% → scale out
- 5-minute cooldown for scale-in

### Background Jobs

Background jobs run in-process by default. To use EventBridge:

1. Enable schedulers in `eventbridge.tf`:
```hcl
state = "ENABLED"
```

2. Disable in-process jobs in FastAPI app

## Monitoring

### CloudWatch Logs

```bash
# View application logs
aws logs tail /ecs/sandbox-broker --follow

# View background job logs
aws logs tail /ecs/sandbox-broker-background-jobs --follow
```

### ECS Service Health

```bash
# Check service status
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker

# View running tasks
aws ecs list-tasks \
  --cluster sandbox-broker-cluster \
  --service-name sandbox-broker
```

### Metrics

Access Prometheus metrics at:
```
http://<alb-dns-name>/metrics
```

## Deployment Updates

### Update Container Image

1. Build and push new image:
```bash
docker build -t sandbox-broker-api:v2 .
docker tag sandbox-broker-api:v2 123456789012.dkr.ecr.us-east-1.amazonaws.com/sandbox-broker-api:v2
docker push 123456789012.dkr.ecr.us-east-1.amazonaws.com/sandbox-broker-api:v2
```

2. Update `terraform.tfvars`:
```hcl
container_image = "123456789012.dkr.ecr.us-east-1.amazonaws.com/sandbox-broker-api:v2"
```

3. Apply changes:
```bash
terraform apply
```

ECS will perform a rolling update with zero downtime.

### Update Secrets

```bash
# Update via AWS CLI
aws secretsmanager update-secret \
  --secret-id sandbox-broker-broker-api-token-xxxxx \
  --secret-string "new-token-value"

# Restart ECS tasks to pick up new secrets
aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker \
  --force-new-deployment
```

## Troubleshooting

### Tasks Not Starting

Check task logs:
```bash
aws logs tail /ecs/sandbox-broker --follow
```

Common issues:
- Invalid secrets (check Secrets Manager)
- Missing IAM permissions
- DynamoDB table not accessible
- Container image not found

### ALB Health Checks Failing

Verify health check endpoint:
```bash
# SSH to ECS task
aws ecs execute-command \
  --cluster sandbox-broker-cluster \
  --task <task-id> \
  --container sandbox-broker \
  --interactive \
  --command "/bin/bash"

# Test health endpoint
curl http://localhost:8080/healthz
```

### High Costs

1. **Reduce NAT Gateway costs**: Use single NAT Gateway or VPC endpoints
2. **Optimize ECS tasks**: Reduce CPU/memory if under-utilized
3. **DynamoDB**: Switch to provisioned capacity for steady workloads
4. **Logs**: Reduce retention period

## Cleanup

**WARNING**: This will delete all resources and data.

```bash
terraform destroy
```

## Remote State (Recommended)

For team collaboration, use S3 backend:

1. Create S3 bucket and DynamoDB table:
```bash
aws s3 mb s3://your-terraform-state-bucket
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST
```

2. Uncomment backend in `main.tf`:
```hcl
backend "s3" {
  bucket         = "your-terraform-state-bucket"
  key            = "sandbox-broker/terraform.tfstate"
  region         = "us-east-1"
  dynamodb_table = "terraform-state-lock"
  encrypt        = true
}
```

3. Initialize:
```bash
terraform init -migrate-state
```

## Security Best Practices

1. **Never commit secrets** to version control
2. **Use IAM roles** instead of access keys when possible
3. **Enable VPC Flow Logs** for network monitoring
4. **Rotate tokens regularly** via Secrets Manager
5. **Use HTTPS** in production with valid certificate
6. **Enable CloudTrail** for audit logging
7. **Review IAM policies** for least privilege

## Support

For issues or questions:
- GitHub Issues: https://github.com/iracic82/Sandbox-API-Broker/issues
- Documentation: https://github.com/iracic82/Sandbox-API-Broker
