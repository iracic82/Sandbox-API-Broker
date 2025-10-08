# Observability & Troubleshooting Guide

**Last Updated**: 2025-10-08
**Environment**: Production (AWS eu-central-1)

---

## 📊 Overview

The Sandbox Broker has comprehensive logging, metrics, and monitoring configured for fast troubleshooting and proactive alerting.

**Observability Score**: 9/10 ⭐⭐⭐⭐⭐

---

## 🔍 CloudWatch Logs

### Log Groups

| Log Group | Retention | Purpose | Size |
|-----------|-----------|---------|------|
| `/ecs/sandbox-broker` | 30 days | API service logs | ~20 MB |
| `/ecs/sandbox-broker-worker` | 30 days | Background worker logs | ~16 KB |
| `/aws/ecs/containerinsights/.../performance` | 1 day | ECS performance metrics | ~3 MB |

### Log Format

All logs use **structured JSON** format:

```json
{
  "timestamp": "2025-10-08T16:40:37.145054Z",
  "level": "INFO",
  "logger": "sandbox_broker",
  "message": "Synced 80 sandboxes, marked 0 as stale",
  "request_id": "job-sync-1759941639",
  "action": "background_sync",
  "outcome": "success",
  "latency_ms": 2599
}
```

**Key Fields**:
- `request_id` - Unique ID for tracing requests
- `action` - What operation was performed
- `outcome` - Result: `success`, `failure`, `error`
- `latency_ms` - Response time in milliseconds
- `level` - Log level: `INFO`, `ERROR`, `WARNING`

---

## 📈 Metric Filters

### API Metrics

| Metric Filter | Pattern | Namespace | Use Case |
|---------------|---------|-----------|----------|
| **APIErrors** | `{ $.level = "ERROR" }` | SandboxBroker | Track all API errors |
| **NoSandboxesAvailable** | `"No sandboxes available"` | SandboxBroker | Alert when pool exhausted |
| **HighLatencyRequests** | `{ $.latency_ms > 1000 }` | SandboxBroker | Track slow requests (>1s) |

### Worker Metrics

| Metric Filter | Pattern | Namespace | Use Case |
|---------------|---------|-----------|----------|
| **WorkerErrors** | `{ $.level = "ERROR" }` | SandboxBroker | Track worker failures |
| **WorkerJobFailures** | `{ $.action = "background_*" && $.outcome = "error" }` | SandboxBroker | Track background job failures |
| **CSPAPIErrors** | `"[ENG CSP]" "error"` | SandboxBroker | Track CSP API failures |

### Viewing Metrics

```bash
# View API errors in last hour
aws cloudwatch get-metric-statistics \
  --namespace SandboxBroker \
  --metric-name APIErrors \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region eu-central-1 \
  --profile okta-sso
```

---

## 🔎 CloudWatch Insights Saved Queries

### 1. **All Errors** (`Sandbox-Broker-All-Errors`)
Find all errors in API logs:
```
fields @timestamp, level, message, request_id, action, outcome
| filter level = "ERROR"
| sort @timestamp desc
| limit 100
```

**Use Case**: Quick error investigation

---

### 2. **Allocation Failures** (`Sandbox-Broker-Allocation-Failures`)
Track failed sandbox allocations:
```
fields @timestamp, message, outcome, latency_ms, track_id
| filter action = "allocate_sandbox" and outcome != "success"
| sort @timestamp desc
| limit 100
```

**Use Case**: Debug allocation issues

---

### 3. **Slow Requests** (`Sandbox-Broker-Slow-Requests`)
Find requests taking >500ms:
```
fields @timestamp, action, latency_ms, outcome, request_id
| filter latency_ms > 500
| sort latency_ms desc
| limit 50
```

**Use Case**: Performance troubleshooting

---

### 4. **Worker Jobs** (`Sandbox-Broker-Worker-Jobs`)
Monitor background job execution:
```
fields @timestamp, message, action, outcome, latency_ms
| filter action like /background/
| sort @timestamp desc
| limit 100
```

**Use Case**: Monitor sync, cleanup, expiry jobs

---

### 5. **Rate Limit Hits** (`Sandbox-Broker-Rate-Limit-Hits`)
Track rate limiting:
```
fields @timestamp, message, request_id
| filter message like /rate limit/
| sort @timestamp desc
| limit 100
```

**Use Case**: Identify clients hitting rate limits

---

### 6. **CSP API Calls** (`Sandbox-Broker-CSP-API-Calls`)
Monitor CSP API interactions:
```
fields @timestamp, message
| filter message like /ENG CSP/
| sort @timestamp desc
| limit 100
```

**Use Case**: Debug CSP integration issues

---

## 🚨 CloudWatch Alarms (Currently Active)

| Alarm | Metric | Threshold | State | Action |
|-------|--------|-----------|-------|--------|
| Auto-Scaling CPU High | CPUUtilization | >70% | OK | Scale up tasks |
| Auto-Scaling CPU Low | CPUUtilization | <30% | ALARM | Scale down tasks |
| Auto-Scaling Memory High | MemoryUtilization | >70% | OK | Scale up tasks |
| Auto-Scaling Memory Low | MemoryUtilization | <30% | ALARM | Scale down tasks |

### Recommended Additional Alarms (TODO)

```bash
# 1. High error rate
Alarm: APIErrors > 10 in 5 minutes
Action: SNS notification

# 2. Pool exhaustion
Alarm: NoSandboxesAvailable > 0
Action: SNS notification + auto-scale sandboxes

# 3. Worker stopped
Alarm: ECS service runningCount = 0
Action: SNS critical alert

# 4. CSP API failures
Alarm: CSPAPIErrors > 5 in 5 minutes
Action: SNS notification
```

---

## 🔧 Troubleshooting Playbooks

### Issue 1: API Returning Errors

**Symptoms**: Increased error rate, 500 responses

**Investigation**:
1. Check CloudWatch Insights query: **All Errors**
2. Look for patterns in error messages
3. Check recent deployments

**Quick Checks**:
```bash
# Check API health
curl https://api-sandbox-broker.highvelocitynetworking.com/healthz

# Check ECS service status
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[0].{running:runningCount,desired:desiredCount}'

# Check recent errors
aws logs tail /ecs/sandbox-broker --since 10m --region eu-central-1 --profile okta-sso | grep ERROR
```

**Common Causes**:
- DynamoDB throttling → Check CloudWatch DynamoDB metrics
- Memory pressure → Check Memory Utilization alarm
- CSP API down → Check Worker CSP API Calls query

---

### Issue 2: No Sandboxes Available

**Symptoms**: Allocation requests failing with "No sandboxes available"

**Investigation**:
1. Check metrics: `broker_pool_available`
2. Run CloudWatch Insights query: **Worker Jobs**
3. Verify sync job is running

**Quick Checks**:
```bash
# Check pool status
curl -s https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep "broker_pool"

# Check when sync last ran
aws logs tail /ecs/sandbox-broker-worker --since 15m --region eu-central-1 --profile okta-sso | grep sync_job

# Check worker service is running
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker-worker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[0].runningCount'
```

**Common Causes**:
- Worker service stopped → Restart worker
- Sync job failing → Check worker logs for CSP API errors
- High allocation rate → All sandboxes legitimately allocated

---

### Issue 3: Slow Performance

**Symptoms**: High latency, timeouts

**Investigation**:
1. Run CloudWatch Insights query: **Slow Requests**
2. Check database performance
3. Check rate limiting

**Quick Checks**:
```bash
# Check p99 latency via Prometheus
curl -s https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep "http_request_duration"

# Check DynamoDB throttling
aws cloudwatch get-metric-statistics \
  --namespace AWS/DynamoDB \
  --metric-name UserErrors \
  --dimensions Name=TableName,Value=sandbox-broker-pool \
  --start-time $(date -u -v-1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region eu-central-1 \
  --profile okta-sso
```

**Common Causes**:
- DynamoDB throttling → Increase provisioned capacity
- /metrics cache disabled → Check cache TTL (should be 60s)
- Rate limiting → Check if client hitting limits

---

### Issue 4: Worker Jobs Not Running

**Symptoms**: Sandboxes not syncing, cleanup not happening

**Investigation**:
1. Check worker service is running
2. Run CloudWatch Insights query: **Worker Jobs**
3. Check for errors in worker logs

**Quick Checks**:
```bash
# Check worker is running
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker-worker \
  --region eu-central-1 \
  --profile okta-sso

# Check worker logs
aws logs tail /ecs/sandbox-broker-worker --follow --region eu-central-1 --profile okta-sso

# Check when jobs last ran
aws logs tail /ecs/sandbox-broker-worker --since 30m --region eu-central-1 --profile okta-sso | grep "Running"
```

**Common Causes**:
- Worker service stopped → Restart with desired count = 1
- CSP API token expired → Update Secrets Manager
- Worker crashed → Check for ERROR logs

---

## 📊 Prometheus Metrics

### Available Metrics

**Pool Status**:
```
broker_pool_total          # Total sandboxes in pool
broker_pool_available      # Available for allocation
broker_pool_allocated      # Currently allocated
broker_pool_pending_deletion  # Marked for deletion
broker_pool_stale          # No longer in CSP
broker_pool_deletion_failed   # Failed to delete
```

**Operations**:
```
broker_allocate_total{outcome}         # Allocations by outcome
broker_allocate_conflicts              # Allocation race conditions
broker_allocate_idempotent_hits        # Idempotent cache hits
broker_deallocate_total{outcome}       # Deallocations by outcome
broker_expiry_total                    # Total expirations
broker_expiry_orphaned                 # Orphaned allocations expired
```

**HTTP**:
```
http_request_duration_seconds{method,endpoint,status}  # Request latency
http_requests_total{method,endpoint,status}            # Request count
```

### Querying Metrics

```bash
# Get current pool status
curl -s https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep "broker_pool"

# Get allocation rate (last 5 minutes)
curl -s https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep "broker_allocate_total"

# Get p99 latency
curl -s https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep "http_request_duration.*quantile.*0.99"
```

---

## 📝 Log Retention & Storage

### CloudWatch Retention

- **API Logs**: 30 days
- **Worker Logs**: 30 days
- **Performance Logs**: 1 day

### S3 Backup

**Bucket**: `s3://sandbox-broker-logs-905418046272/`

**Current Backups**:
```
api-logs-20251008.txt (11.2 MB)
worker-logs-20251008.txt (16.4 KB)
```

**Recommended**: Set up automated daily exports

```bash
# Manual export
aws logs tail /ecs/sandbox-broker --since 24h --region eu-central-1 --profile okta-sso > api-logs-$(date +%Y%m%d).txt
aws s3 cp api-logs-$(date +%Y%m%d).txt s3://sandbox-broker-logs-905418046272/
```

---

## 🔐 Security Monitoring

### What's Logged

✅ **Logged**:
- Request IDs (for tracing)
- Action types
- Response times
- Error messages
- Authentication outcomes (success/failure only)
- Rate limit hits

❌ **NOT Logged** (Security):
- API tokens (masked)
- AWS credentials (never logged)
- Sensitive user data
- Full authorization headers

### Security Audit Checklist

```bash
# 1. Check for unauthorized access attempts
Run CloudWatch Insights: filter message like /401|403/

# 2. Check for rate limit abuse
Run saved query: "Sandbox-Broker-Rate-Limit-Hits"

# 3. Check for suspicious error patterns
Run saved query: "Sandbox-Broker-All-Errors"

# 4. Check worker job integrity
Run saved query: "Sandbox-Broker-Worker-Jobs"
```

---

## 🎯 Performance Baselines

### Normal Operation

| Metric | Expected Value | Alert Threshold |
|--------|----------------|-----------------|
| API Error Rate | <0.1% | >1% |
| p50 Latency | <50ms | >200ms |
| p99 Latency | <500ms | >2000ms |
| Pool Available | >10 | <5 |
| Worker Job Success Rate | >99% | <95% |
| Sync Job Duration | <5s | >30s |
| Cleanup Job Duration | <5s | >30s |

### Load Testing Results

- **Concurrent Allocations**: 200/min sustained
- **Peak Throughput**: 300 requests/min
- **p99 Latency @ 200 req/min**: 450ms
- **Rate Limit**: 100 requests/min per client

---

## 📞 Quick Reference Commands

### Check Service Health
```bash
# API health
curl https://api-sandbox-broker.highvelocitynetworking.com/healthz

# Pool status
curl -s https://api-sandbox-broker.highvelocitynetworking.com/metrics | grep broker_pool

# ECS services
aws ecs describe-services \
  --cluster sandbox-broker-cluster \
  --services sandbox-broker sandbox-broker-worker \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'services[*].{Name:serviceName,Running:runningCount,Desired:desiredCount}' \
  --output table
```

### View Recent Logs
```bash
# API logs (last 10 minutes)
aws logs tail /ecs/sandbox-broker --since 10m --region eu-central-1 --profile okta-sso

# Worker logs (last 10 minutes)
aws logs tail /ecs/sandbox-broker-worker --since 10m --region eu-central-1 --profile okta-sso

# Follow logs live
aws logs tail /ecs/sandbox-broker --follow --region eu-central-1 --profile okta-sso
```

### Run CloudWatch Insights Queries
```bash
# List all saved queries
aws logs describe-query-definitions \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'queryDefinitions[?contains(name, `Sandbox-Broker`)].name'

# Run query manually
aws logs start-query \
  --log-group-name /ecs/sandbox-broker \
  --start-time $(date -u -v-1H +%s) \
  --end-time $(date -u +%s) \
  --query-string 'fields @timestamp, level, message | filter level = "ERROR" | sort @timestamp desc | limit 20' \
  --region eu-central-1 \
  --profile okta-sso
```

---

## 🔄 Future Enhancements

### Short Term
- [ ] Set up SNS topics for alerts
- [ ] Configure alarms for metric filters
- [ ] Enable VPC Flow Logs
- [ ] Create Lambda for automated log analysis

### Long Term
- [ ] Enable AWS X-Ray for distributed tracing
- [ ] Set up Grafana dashboards
- [ ] Implement log aggregation with OpenSearch
- [ ] Add custom business metrics

---

**Last Review**: 2025-10-08
**Next Review**: 2025-10-15
