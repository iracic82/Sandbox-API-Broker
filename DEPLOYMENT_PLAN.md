# Production Deployment Plan - AWS CLI with okta-sso

**Date**: 2025-10-08
**Changes**: Critical bug fixes + worker service
**Risk Level**: 🟡 MEDIUM
**Estimated Time**: 30-45 minutes
**Rollback Time**: 5 minutes

---

## **Pre-Deployment Checklist**

- [ ] All tests passed locally (see `TESTING_PLAN.md`)
- [ ] Code reviewed (`FIXES_SUMMARY.md`)
- [ ] Terraform plan reviewed
- [ ] Have AWS CLI access via okta-sso
- [ ] Have rollback plan ready
- [ ] Monitor CloudWatch ready

---

## **Step 0: AWS Authentication**

```bash
# Authenticate with okta-sso
aws-okta exec okta-sso -- aws sts get-caller-identity

# Verify you're using the correct AWS account
# Expected output should show account 905418046272
```

---

## **Step 1: Build and Push Docker Image**

```bash
# Set variables
export AWS_ACCOUNT_ID=905418046272
export AWS_REGION=eu-central-1
export ECR_REPO=sandbox-broker-api
export IMAGE_TAG=$(git rev-parse --short HEAD)  # e.g., "a8225a5"

# Build Docker image (platform must be linux/amd64 for ECS)
docker build --platform linux/amd64 -t ${ECR_REPO}:${IMAGE_TAG} .

# Tag for ECR
docker tag ${ECR_REPO}:${IMAGE_TAG} \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}

docker tag ${ECR_REPO}:${IMAGE_TAG} \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest

# Login to ECR
aws-okta exec okta-sso -- aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin \
  ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Push to ECR
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:${IMAGE_TAG}
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest

echo "✅ Docker image pushed: ${IMAGE_TAG}"
```

---

## **Step 2: Review Terraform Changes**

```bash
cd terraform/

# Initialize Terraform
aws-okta exec okta-sso -- terraform init

# Review planned changes
aws-okta exec okta-sso -- terraform plan -out=tfplan

# Expected changes:
# + aws_ecs_task_definition.worker
# + aws_ecs_service.worker
# + aws_cloudwatch_log_group.worker
# + aws_cloudwatch_metric_alarm.worker_cpu_high
# + aws_cloudwatch_metric_alarm.worker_memory_high
# ~ aws_ecs_task_definition.sandbox_broker_api (will be updated)
#
# Total: 5 new resources, 1 modified
```

**⚠️ IMPORTANT**: Review the plan carefully. Make sure:
- Worker service is being created (1 task)
- API service is NOT being destroyed
- No unexpected changes

---

## **Step 3: Apply Terraform (Create Worker Service)**

```bash
# Apply changes
aws-okta exec okta-sso -- terraform apply tfplan

# Wait for completion (2-3 minutes)
# Expected output:
# aws_ecs_service.worker: Creating...
# aws_ecs_service.worker: Creation complete after 2m15s

echo "✅ Worker service created"
```

---

## **Step 4: Verify Worker Service Started**

```bash
# Check worker service status
aws-okta exec okta-sso -- aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker-worker \
  --region ${AWS_REGION}

# Expected:
# "runningCount": 1
# "desiredCount": 1

# Check worker logs
aws-okta exec okta-sso -- aws logs tail /ecs/sandbox-broker-worker --follow --region ${AWS_REGION}

# Expected output:
# 🚀 Sandbox Broker Worker v0.1.0 starting...
# ✅ Started 4 background jobs
```

**✅ Checkpoint**: Worker should be running and healthy

---

## **Step 5: Update API Service (Remove Background Jobs)**

The API task definition was already updated by Terraform in Step 3.
Now we need to force a new deployment to pick up the new task definition.

```bash
# Force new deployment of API service
aws-okta exec okta-sso -- aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker-api \
  --force-new-deployment \
  --region ${AWS_REGION}

# Wait for deployment (3-5 minutes)
# Monitor deployment status
aws-okta exec okta-sso -- aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker-api \
  --region ${AWS_REGION} \
  --query 'services[0].deployments'

# Expected:
# "desiredCount": 2
# "runningCount": 2
# "status": "PRIMARY"
```

---

## **Step 6: Verify API Service Health**

```bash
# Check API health
curl -f https://api-sandbox-broker.highvelocitynetworking.com/healthz

# Expected:
# {"status":"healthy","timestamp":1759687514}

# Check API logs
aws-okta exec okta-sso -- aws logs tail /ecs/sandbox-broker-api --follow --region ${AWS_REGION}

# Expected output:
# 🚀 Sandbox Broker API v0.1.0 starting...
# ℹ️  Background jobs are handled by separate worker service
```

**✅ Checkpoint**: API should be healthy, NO background jobs starting

---

## **Step 7: Verify Fixes Work**

### Test 1: Rate Limiter Accepts New Header

```bash
# Test with X-Instruqt-Sandbox-ID (new preferred header)
curl -H "Authorization: Bearer YOUR_API_TOKEN" \
     -H "X-Instruqt-Sandbox-ID: test-sandbox-123" \
     https://api-sandbox-broker.highvelocitynetworking.com/healthz

# Should return 200 OK
# Should include X-RateLimit-Limit header
```

### Test 2: CORS Allows New Headers

```bash
# Preflight request
curl -X OPTIONS \
     -H "Origin: https://instruqt.com" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: X-Instruqt-Sandbox-ID" \
     https://api-sandbox-broker.highvelocitynetworking.com/healthz \
     -v

# Should return 200 OK
# Should include: Access-Control-Allow-Headers: X-Instruqt-Sandbox-ID
```

### Test 3: Worker Jobs Running

```bash
# Check worker logs for job execution
aws-okta exec okta-sso -- aws logs tail /ecs/sandbox-broker-worker --follow --region ${AWS_REGION}

# Should see (within 10 minutes):
# [sync_job] Running sync...
# [cleanup_job] Running cleanup...
# [auto_expiry_job] Checked X allocations...
```

### Test 4: Metrics Endpoint Performance

```bash
# First request (should scan DB)
time curl https://api-sandbox-broker.highvelocitynetworking.com/metrics

# Second request (should use cache, faster)
time curl https://api-sandbox-broker.highvelocitynetworking.com/metrics

# Second request should be noticeably faster (<50ms vs ~200ms)
```

---

## **Step 8: Monitor for 1 Hour**

```bash
# Monitor both services
watch -n 30 'aws-okta exec okta-sso -- aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker-api sandbox-broker-worker \
  --region eu-central-1 \
  --query "services[*].[serviceName,runningCount,desiredCount]"'

# Expected output every 30 seconds:
# sandbox-broker-api      2  2
# sandbox-broker-worker   1  1
```

**Monitor CloudWatch**:
- API service logs: `/ecs/sandbox-broker-api`
- Worker service logs: `/ecs/sandbox-broker-worker`
- Look for errors, warnings

**Monitor Metrics**:
```bash
# Check metrics are being updated
curl https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep pool_total
```

---

## **Step 9: Production CORS Update (IMPORTANT)**

⚠️ **After confirming everything works**, update CORS to restrict origins:

```bash
# Update ECS task definition environment variables
# Edit the task definition JSON to set:
# CORS_ALLOWED_ORIGINS=https://your-instruqt-domain.com,https://app2.example.com

# OR update via Terraform variables and re-apply
```

**For now**: Leave as `*` to maintain compatibility, but add this to your post-deployment tasks.

---

## **Rollback Plan** 🔴

If anything goes wrong:

### Rollback Worker Service:

```bash
# Stop worker service
aws-okta exec okta-sso -- aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker-worker \
  --desired-count 0 \
  --region ${AWS_REGION}
```

### Rollback API Service:

```bash
# Get previous task definition
aws-okta exec okta-sso -- aws ecs describe-task-definition \
  --task-definition sandbox-broker-api \
  --region ${AWS_REGION} \
  --query 'taskDefinition.revision'

# Rollback to previous revision (e.g., revision 5)
aws-okta exec okta-sso -- aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker-api \
  --task-definition sandbox-broker-api:5 \
  --force-new-deployment \
  --region ${AWS_REGION}
```

### Full Rollback (Nuclear Option):

```bash
cd terraform/
aws-okta exec okta-sso -- terraform destroy -target=aws_ecs_service.worker
aws-okta exec okta-sso -- terraform destroy -target=aws_ecs_task_definition.worker

# Then re-enable background jobs in API (would require code change)
```

**Estimated Rollback Time**: 5 minutes

---

## **Post-Deployment Checklist**

- [ ] API service healthy (2 tasks running)
- [ ] Worker service healthy (1 task running)
- [ ] Rate limiter accepts `X-Instruqt-Sandbox-ID`
- [ ] CORS allows new headers
- [ ] Worker jobs running (check logs)
- [ ] Metrics endpoint fast (cached)
- [ ] No errors in CloudWatch logs
- [ ] Monitor for 1 hour
- [ ] Update CORS origins (post-deployment task)

---

## **Success Criteria**

✅ **Deployment Successful If**:
1. Both services running (API: 2 tasks, Worker: 1 task)
2. API responds to health checks
3. Worker logs show background jobs running
4. No errors in CloudWatch logs
5. All fixes verified working

---

## **Troubleshooting**

### Worker Service Won't Start

```bash
# Check logs
aws-okta exec okta-sso -- aws logs tail /ecs/sandbox-broker-worker --follow --region ${AWS_REGION}

# Common issues:
# - Missing environment variables → Check task definition
# - DynamoDB permissions → Check IAM role
# - CSP API token invalid → Check CSP_API_TOKEN
```

### API Service Degraded

```bash
# Check running tasks
aws-okta exec okta-sso -- aws ecs list-tasks \
  --cluster sandbox-broker-cluster \
  --service-name sandbox-broker-api \
  --region ${AWS_REGION}

# Check task health
aws-okta exec okta-sso -- aws ecs describe-tasks \
  --cluster sandbox-broker-cluster \
  --tasks TASK_ARN \
  --region ${AWS_REGION}
```

---

**Status**: Ready for deployment
**Next**: Run local tests (`TESTING_PLAN.md`), then execute this deployment plan
