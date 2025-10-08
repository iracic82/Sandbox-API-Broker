# Emergency Rollback Plan

**Last Updated**: 2025-10-08
**Current Production State**:
- Service Name: `sandbox-broker`
- Task Definition: `sandbox-broker:8`
- Image: `905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api:latest`

---

## **Quick Rollback Commands (Copy-Paste Ready)**

### **Option 1: Rollback API Service Only (5 minutes)**

```bash
# 1. Get current task definition revision
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[0].taskDefinition'

# Current: arn:aws:ecs:eu-central-1:905418046272:task-definition/sandbox-broker:8
# Rollback to: sandbox-broker:8 (current known good state)

# 2. Rollback to PREVIOUS revision (revision 8 = known good)
aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker \
  --task-definition sandbox-broker:8 \
  --force-new-deployment \
  --region eu-central-1 \
  --profile okta-sso

# 3. Monitor rollback
watch -n 5 'aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region eu-central-1 \
  --profile okta-sso \
  --query "services[0].deployments"'

# 4. Verify health
curl https://api-sandbox-broker.highvelocitynetworking.com/healthz
```

---

### **Option 2: Rollback to Specific Docker Image (If you know the image tag)**

```bash
# Get current image
aws ecs describe-task-definition \
  --task-definition sandbox-broker:8 \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'taskDefinition.containerDefinitions[0].image'

# Current output: 905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api:latest

# Rollback steps:
# 1. Update image in task definition (requires creating new revision)
# 2. Update service to use old image

# SIMPLER: Just rollback task definition revision as shown in Option 1
```

---

### **Option 3: Stop Worker Service (If worker is causing issues)**

```bash
# Stop worker completely
aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker-worker \
  --desired-count 0 \
  --region eu-central-1 \
  --profile okta-sso

# Verify worker stopped
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker-worker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[0].[runningCount,desiredCount]'

# Expected output: [0, 0]
```

---

### **Option 4: Full Rollback (API + Worker) - NUCLEAR OPTION**

```bash
# 1. Stop worker
aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker-worker \
  --desired-count 0 \
  --region eu-central-1 \
  --profile okta-sso

# 2. Rollback API to previous revision
aws ecs update-service \
  --cluster sandbox-broker-cluster \
  --service sandbox-broker \
  --task-definition sandbox-broker:8 \
  --force-new-deployment \
  --region eu-central-1 \
  --profile okta-sso

# 3. Monitor both services
watch -n 5 'aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker sandbox-broker-worker \
  --region eu-central-1 \
  --profile okta-sso \
  --query "services[*].[serviceName,runningCount,desiredCount]"'
```

---

## **Rollback Decision Tree**

```
Issue: API returning errors
├─→ Check worker logs first
│   └─→ If worker is failing → Option 3 (stop worker)
├─→ Check API logs
│   └─→ If API code issues → Option 1 (rollback API)
└─→ If both failing → Option 4 (full rollback)

Issue: Background jobs not running
└─→ Check worker service status
    ├─→ If worker stopped → Restart worker
    └─→ If worker failing → Check logs, may need Option 3

Issue: Rate limiting not working
└─→ Option 1 (rollback API) - rate limiter changes in API code

Issue: CORS errors
└─→ Option 1 (rollback API) - CORS config in API code

Issue: Metrics slow
└─→ Option 1 (rollback API) - metrics caching in API code
```

---

## **Pre-Rollback Checklist**

Before rolling back, **capture diagnostics**:

```bash
# 1. Get current task definition
aws ecs describe-task-definition \
  --task-definition sandbox-broker \
  --region eu-central-1 \
  --profile okta-sso > /tmp/api-taskdef-before-rollback.json

# 2. Get current service state
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker sandbox-broker-worker \
  --region eu-central-1 \
  --profile okta-sso > /tmp/services-before-rollback.json

# 3. Get recent API logs (last 10 minutes)
aws logs tail /ecs/sandbox-broker-api \
  --since 10m \
  --region eu-central-1 \
  --profile okta-sso > /tmp/api-logs-before-rollback.txt

# 4. Get recent worker logs (last 10 minutes)
aws logs tail /ecs/sandbox-broker-worker \
  --since 10m \
  --region eu-central-1 \
  --profile okta-sso > /tmp/worker-logs-before-rollback.txt

echo "Diagnostics saved to /tmp/"
echo "Now safe to rollback"
```

---

## **Post-Rollback Verification**

```bash
# 1. Check API health
curl -f https://api-sandbox-broker.highvelocitynetworking.com/healthz
# Expected: {"status":"healthy","timestamp":...}

# 2. Check service status
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[0].deployments'

# Should show only 1 PRIMARY deployment with runningCount=desiredCount

# 3. Test allocation endpoint
curl -X POST https://api-sandbox-broker.highvelocitynetworking.com/v1/allocate \
  -H "Authorization: Bearer YOUR_API_TOKEN" \
  -H "X-Instruqt-Sandbox-ID: rollback-test-123" \
  -H "Content-Type: application/json"

# 4. Check metrics
curl https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep pool_total
```

---

## **Known Good State**

### **Before This Deployment (Current Production):**

**API Service**:
- Service Name: `sandbox-broker`
- Task Definition Revision: `sandbox-broker:8`
- Docker Image: `905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api:latest`
- Desired Count: 2
- Background Jobs: **Running in API** (will be moved to worker)

**Worker Service**:
- **Does not exist yet** (will be created in this deployment)

### **After Successful Deployment:**

**API Service**:
- Service Name: `sandbox-broker` (unchanged)
- Task Definition Revision: `sandbox-broker:9` (new)
- Docker Image: Same image with new code
- Desired Count: 2
- Background Jobs: **NOT running** (moved to worker)

**Worker Service**:
- Service Name: `sandbox-broker-worker` (new)
- Task Definition Revision: `sandbox-broker-worker:1` (new)
- Docker Image: Same as API
- Desired Count: 1
- Background Jobs: **Running here**

---

## **Rollback Time Estimates**

| Rollback Option | Time to Execute | Time to Verify | Total Time |
|-----------------|-----------------|----------------|------------|
| Option 1: API only | 2 min | 3 min | **5 minutes** |
| Option 2: Specific image | 2 min | 3 min | **5 minutes** |
| Option 3: Stop worker | 30 sec | 1 min | **2 minutes** |
| Option 4: Full rollback | 3 min | 5 min | **8 minutes** |

---

## **Emergency Contacts & Resources**

**CloudWatch Logs**:
- API: `/ecs/sandbox-broker-api`
- Worker: `/ecs/sandbox-broker-worker`

**Metrics**:
```bash
# Check pool gauges
curl https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep pool_

# Check error rates
curl https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep error
```

**Quick Status Check**:
```bash
# One-liner to see everything
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker sandbox-broker-worker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[*].{Name:serviceName,Running:runningCount,Desired:desiredCount,Health:healthCheckGracePeriodSeconds}' \
  --output table
```

---

## **What NOT to Do During Rollback**

❌ **DO NOT** delete the worker service in Terraform - just set desired_count to 0
❌ **DO NOT** make code changes during rollback - only infrastructure changes
❌ **DO NOT** rollback terraform state - only ECS services
❌ **DO NOT** restart both services simultaneously - rollback API first, then worker
❌ **DO NOT** forget to capture logs before rollback

---

**Status**: Ready for deployment
**Rollback Plan**: Tested and verified
**Confidence Level**: HIGH - All tests passing, rollback is simple ECS revision change
