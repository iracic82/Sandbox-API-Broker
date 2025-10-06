# API Limits and Constraints

> Comprehensive documentation of all rate limits, capacity constraints, and API limitations for the Sandbox Broker API

## Table of Contents

- [Overview](#overview)
- [Application Rate Limits](#application-rate-limits)
- [AWS WAF Rate Limits](#aws-waf-rate-limits)
- [DynamoDB Capacity](#dynamodb-capacity)
- [Network and Infrastructure Limits](#network-and-infrastructure-limits)
- [Single IP Behavior](#single-ip-behavior)
- [Testing Considerations](#testing-considerations)
- [Troubleshooting Rate Limit Errors](#troubleshooting-rate-limit-errors)
- [Request Limit Increases](#request-limit-increases)
- [Technical Implementation](#technical-implementation)

---

## Overview

The Sandbox Broker API implements multiple layers of rate limiting and capacity constraints to ensure:
- ✅ **Fair resource allocation** across all users
- ✅ **Protection against abuse** and DDoS attacks
- ✅ **System stability** under high load
- ✅ **Cost control** for AWS resources

**Layered Protection:**
```
┌─────────────────────────────────────┐
│  1. AWS WAF (2000 req/5min per IP) │
├─────────────────────────────────────┤
│  2. ALB (Connection limits)         │
├─────────────────────────────────────┤
│  3. Application (50 RPS, burst 200) │
├─────────────────────────────────────┤
│  4. DynamoDB (Auto-scaling)         │
└─────────────────────────────────────┘
```

---

## Application Rate Limits

### Token Bucket Algorithm

The API uses a **token bucket** rate limiting algorithm implemented in `app/middleware/rate_limit.py`.

**Configuration:**
```python
# app/main.py
app.add_middleware(
    RateLimitMiddleware,
    requests_per_second=50,  # Sustained rate
    burst=200                # Burst capacity
)
```

### How It Works

1. **Bucket starts with 200 tokens** (burst capacity)
2. **Each request consumes 1 token**
3. **Tokens refill at 50/second**
4. **If bucket is empty → 429 Rate Limit Exceeded**

**Refill Calculation:**
```
Time to refill from empty to full = 200 tokens ÷ 50 tokens/sec = 4 seconds
```

### Performance Characteristics

| Scenario | Requests | Duration | Result | Explanation |
|----------|----------|----------|--------|-------------|
| **Instant burst** | 200 | 0s | ✅ All succeed | Burst capacity |
| **Large burst** | 300 | 0s | ⚠️ 100 fail | Exceeds burst (200) |
| **Sustained load** | 500 | 10s | ✅ All succeed | 500 RPS avg within limits |
| **High sustained** | 1000 | 10s | ⚠️ ~500 fail | 100 RPS avg exceeds 50 RPS limit |
| **Large event** | 200 | instant | ✅ All succeed | Training event with 200 students |
| **Back-to-back events** | 200 + 200 | 0s + 4s | ✅ All succeed | Second event after 4s refill |

### Rate Limit Response Headers

**Every API response includes:**
```http
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 157
X-RateLimit-Reset: 1696512345
```

**Field Descriptions:**
- `X-RateLimit-Limit`: Total burst capacity (200)
- `X-RateLimit-Remaining`: Tokens left in bucket
- `X-RateLimit-Reset`: Unix timestamp when bucket will be full

### 429 Response Format

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Retry after 2 seconds.",
    "retry_after": 2,
    "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
  }
}
```

**HTTP Headers:**
```http
HTTP/1.1 429 Too Many Requests
Retry-After: 2
X-RateLimit-Limit: 200
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1696512347
```

### Scope and Granularity

**Per-Client IP (as seen by ALB):**
- Rate limits are applied per source IP address
- ALB extracts original client IP from `X-Forwarded-For` header
- Multiple ECS tasks share rate limit state (in-memory, eventually consistent)

**Important:** If 50 students connect from the same corporate NAT IP, they share the same rate limit allowance.

---

## AWS WAF Rate Limits

### Configuration

**AWS Web Application Firewall** provides an additional protection layer at the load balancer level.

**Rule:** `sandbox-broker-rate-limit-rule`
```
Limit: 2000 requests per 5 minutes per source IP
Action: Block (403 Forbidden)
```

### How It Works

1. **WAF tracks requests** by source IP address (before ALB)
2. **Counter increments** with each request
3. **Counter resets** after 5 minutes
4. **Blocked for 5 minutes** after exceeding limit

**Timeline Example:**
```
T+0:00  → Student makes 1st request (counter: 1)
T+0:10  → Student makes 2000th request (counter: 2000)
T+0:11  → Student makes 2001st request → 403 Forbidden (blocked)
T+5:00  → Counter resets (student can retry)
```

### WAF Response

```http
HTTP/1.1 403 Forbidden
Content-Type: application/json

{
  "message": "Forbidden"
}
```

**Note:** WAF responses are generic and don't include rate limit details.

### When WAF Blocks Occur

**Real-World Scenarios:**

| Scenario | Requests in 5 min | Result |
|----------|-------------------|--------|
| Normal student | 3-10 | ✅ No issue |
| Misbehaving script (polling) | 3000+ | ❌ Blocked |
| Load test (single machine) | 5000+ | ❌ Blocked |
| 100 students (different IPs) | 100 × 10 = 1000 | ✅ Each has own allowance |

**Key Insight:** Real students from different IPs each get 2000 req/5min. This is a **very generous** limit for normal usage.

---

## DynamoDB Capacity

### Table Configuration

**Mode:** On-Demand (auto-scaling)
```
Table: sandbox-broker-pool
Billing: On-Demand (pay per request)
Region: eu-central-1
```

### Capacity Limits

**On-Demand Mode:**
- **Write Capacity**: Auto-scales up to **40,000 WCU**
- **Read Capacity**: Auto-scales up to **40,000 RCU**
- **Throttling**: Rare, only during extreme spikes

**Request Units:**
- 1 WCU = 1 write up to 1 KB
- 1 RCU = 1 strongly consistent read up to 4 KB

### Typical Operation Costs

| Operation | Reads | Writes | Total RCU/WCU |
|-----------|-------|--------|---------------|
| **Allocate** | 1-3 | 2 | 3 RCU, 2 WCU |
| **Mark for deletion** | 1 | 1 | 1 RCU, 1 WCU |
| **Get sandbox** | 1 | 0 | 1 RCU |
| **Admin stats** | 25+ | 0 | 25+ RCU |
| **Sync (100 sandboxes)** | 100 | 5-10 | 100 RCU, 5-10 WCU |

### Performance Characteristics

**Burst Allocation Example:**
```
200 concurrent allocations
= 200 × (3 RCU + 2 WCU)
= 600 RCU + 400 WCU

This is well within DynamoDB's auto-scaling capacity (40,000 WCU/RCU)
```

### Global Secondary Indexes (GSIs)

**3 GSIs with separate capacity:**

1. **StatusIndex** (GSI1): `status` + `allocated_at`
   - Used by: allocation service, admin endpoints
   - Typical load: Medium (queries for available sandboxes)

2. **TrackIndex** (GSI2): `allocated_to_track` + `allocated_at`
   - Used by: admin queries, analytics
   - Typical load: Low (admin operations only)

3. **IdempotencyIndex** (GSI3): `idempotency_key` + `allocated_at`
   - Used by: allocation service (idempotency checks)
   - Typical load: High (every allocation request)

**Note:** Each GSI auto-scales independently.

### Throttling Behavior

**When it happens:**
- Sustained load >1000 RPS for several minutes
- Sudden spike >5000 RPS (rare with on-demand)

**Response:**
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Database temporarily unavailable. Retry after 100ms.",
    "request_id": "..."
  }
}
```

**Resolution:** Auto-scaling kicks in within seconds. Exponential backoff recommended.

---

## Network and Infrastructure Limits

### Application Load Balancer (ALB)

**Configuration:**
- **Scheme:** Internet-facing
- **Subnets:** 2 public subnets (multi-AZ)
- **Target Group:** ECS Fargate tasks (2-10 tasks)

**Limits:**
- **Connections per target:** 1000 (default)
- **New connections per second:** ~10,000
- **Request timeout:** 60 seconds
- **Idle timeout:** 60 seconds

**In practice:** ALB limits are unlikely to be reached before application rate limits.

### ECS Fargate Tasks

**Current Configuration:**
```
Service: sandbox-broker-service
Cluster: sandbox-broker-cluster
Tasks: 2 (minimum) to 10 (maximum)
CPU: 1 vCPU per task
Memory: 2 GB per task
```

**Auto-Scaling Policy:**
```yaml
Target Metric: CPU Utilization
Target Value: 70%
Scale-Out: Add 1 task when CPU > 70% for 2 min
Scale-In: Remove 1 task when CPU < 50% for 5 min
```

**Task Capacity:**
- Each task handles ~100-200 RPS comfortably
- 2 tasks = ~200-400 RPS total capacity
- 10 tasks = ~1000-2000 RPS total capacity

**Connection Pooling:**
- DynamoDB SDK: Default connection pool (50 connections)
- HTTP client (CSP API): Connection pool (10 connections)

---

## Single IP Behavior

### Understanding Source IP

**Request Flow:**
```
Student (IP: 203.0.113.45)
  ↓
  │ X-Forwarded-For: 203.0.113.45
  ↓
AWS WAF (checks 203.0.113.45) → WAF rate limit (2000/5min)
  ↓
ALB (preserves X-Forwarded-For)
  ↓
ECS Task (extracts 203.0.113.45) → App rate limit (50 RPS, burst 200)
  ↓
DynamoDB
```

### Scenarios

#### Scenario 1: Multiple Students, Different IPs (Normal)

**Setup:**
- 100 students from different locations
- Each student: unique public IP

**Result:**
- ✅ Each student gets own WAF allowance (2000 req/5min)
- ✅ Each student gets own app allowance (50 RPS, burst 200)
- ✅ No interference between students

**Total Capacity:**
- 100 students × 200 burst = **20,000 concurrent allocations** ✅

#### Scenario 2: Multiple Students, Same IP (Corporate NAT)

**Setup:**
- 50 students from same office
- All behind same corporate NAT (IP: 198.51.100.10)

**Result:**
- ⚠️ All 50 students **share** WAF allowance (2000 req/5min total)
- ⚠️ All 50 students **share** app allowance (50 RPS, burst 200 total)

**Impact:**
- 50 students allocate simultaneously → 50 requests → ✅ Succeeds (within burst 200)
- 300 students allocate simultaneously → 300 requests → ⚠️ 100 get 429 errors

**Mitigation:**
- Students retry after 1-2 seconds → ✅ Tokens refilled
- Instruqt staggers lab starts naturally

#### Scenario 3: Load Testing (Single Machine)

**Setup:**
- k6 running on one machine
- Testing with 150 VUs

**Result:**
- ⚠️ All 150 VUs share single IP
- ⚠️ Will hit app rate limits quickly
- ⚠️ Will hit WAF limits after 2000 requests

**Solutions:**
- Use distributed load testing (k6 cloud)
- Temporarily whitelist test IP in WAF
- Reduce VUs to stay under limits

---

## Testing Considerations

### Local Testing (DynamoDB Local)

**No rate limits by default** in docker-compose.yml for local development.

**To enable rate limits locally:**
```bash
# Edit docker-compose.yml
environment:
  - ENABLE_RATE_LIMITS=true

# Restart services
docker compose down && docker compose up -d
```

### Load Testing

**Production Load Test Example (from session):**
```javascript
// k6 script
export const options = {
  scenarios: {
    concurrent_allocation: {
      executor: 'shared-iterations',
      vus: 150,           // 150 concurrent students
      iterations: 150,    // 150 total allocations
      maxDuration: '60s',
    },
  },
};
```

**Results (150 concurrent students):**
- **Before rate limit increase** (burst=20): 74.67% success rate
- **After rate limit increase** (burst=200): 100% success rate expected

**Key Findings:**
1. Rate limiter was the bottleneck (not DynamoDB or allocation logic)
2. Zero double-allocations in all tests ✅
3. Name filtering works perfectly at scale ✅

### Best Practices for Load Testing

**1. Use Distributed Testing:**
```bash
# k6 Cloud (distributed across multiple IPs)
k6 cloud script.js

# AWS Distributed Load Testing Solution
# https://aws.amazon.com/solutions/implementations/distributed-load-testing-on-aws/
```

**2. Temporarily Adjust WAF (if needed):**
```bash
# Whitelist your IP during testing
aws wafv2 update-ip-set \
  --id <ip-set-id> \
  --addresses "203.0.113.45/32" \
  --scope REGIONAL \
  --region eu-central-1
```

**3. Seed Test Data:**
```python
# Use test sandbox_id prefix to avoid production data
sandbox_id_prefix = "9"  # 9001-9200 for tests
```

**4. Clean Up After Tests:**
```bash
# Delete all test sandboxes
curl -X POST "https://api.../v1/admin/bulk-delete?status=allocated" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Troubleshooting Rate Limit Errors

### Error: 429 Rate Limit Exceeded

**Symptom:**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded. Retry after 2 seconds.",
    "retry_after": 2
  }
}
```

**Cause:** Application token bucket empty (exceeded 200 burst or 50 RPS sustained)

**Solution:**

**1. Implement Exponential Backoff:**
```python
import time
import random

def allocate_with_retry(max_retries=5):
    for attempt in range(max_retries):
        response = requests.post(url, headers=headers)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            retry_after = response.json()["error"].get("retry_after", 1)
            # Exponential backoff with jitter
            sleep_time = (2 ** attempt) * retry_after + random.uniform(0, 1)
            print(f"Rate limited. Retrying in {sleep_time:.2f}s...")
            time.sleep(sleep_time)
            continue

        # Other errors
        raise Exception(f"Error: {response.status_code}")

    raise Exception("Max retries exceeded")
```

**2. Monitor Rate Limit Headers:**
```python
def check_rate_limits(response):
    remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
    reset = int(response.headers.get("X-RateLimit-Reset", 0))

    if remaining < 20:
        wait_time = reset - time.time()
        print(f"⚠️ Low tokens: {remaining} remaining. Bucket refills in {wait_time:.1f}s")

        if remaining < 5:
            time.sleep(2)  # Slow down proactively
```

**3. Reduce Request Rate:**
```python
# Add delay between requests
for student in students:
    allocate_sandbox(student)
    time.sleep(0.1)  # 10 RPS (well under 50 RPS limit)
```

### Error: 403 Forbidden (WAF Block)

**Symptom:**
```json
{
  "message": "Forbidden"
}
```

**Cause:** AWS WAF blocked request (exceeded 2000 req/5min from single IP)

**Solution:**

**1. Wait 5 Minutes:**
```python
# WAF counter resets after 5 minutes
if response.status_code == 403:
    print("WAF blocked. Waiting 5 minutes...")
    time.sleep(300)
    retry()
```

**2. Use Distributed Testing:**
```bash
# Instead of single machine
k6 run script.js  # ❌ Single IP

# Use k6 Cloud (multiple IPs)
k6 cloud script.js  # ✅ Distributed
```

**3. Contact Admin for Whitelist:**
```
If your organization consistently hits WAF limits during normal usage,
request IP whitelist from API administrators.
```

### Error: 500 Internal Error (DynamoDB Throttling)

**Symptom:**
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred"
  }
}
```

**Cause:** DynamoDB throttling (very rare with on-demand mode)

**Solution:**
- Retry with exponential backoff
- DynamoDB auto-scaling resolves within seconds

---

## Request Limit Increases

### When to Request Increases

**Consider requesting higher limits if:**
- Consistent 429 errors during normal operations
- Large training events (>200 concurrent students)
- Multiple students behind same corporate NAT
- High-frequency polling required (not recommended)

### Information to Provide

**When requesting limit increases, include:**

1. **Current Usage:**
   - Average RPS during normal operations
   - Peak RPS during events
   - 95th/99th percentile latency

2. **Use Case:**
   - Number of concurrent students expected
   - Geographic distribution (multiple IPs?)
   - Frequency of requests per student

3. **Proposed Limits:**
   - Desired sustained RPS
   - Desired burst capacity

**Example Request:**
```
Subject: Rate Limit Increase Request

Current Limits: 50 RPS sustained, 200 burst
Requested Limits: 100 RPS sustained, 500 burst

Use Case:
- Training events with 400+ students
- Students allocated across multiple regions (100+ unique IPs)
- Each student: 1 allocation + 1 deletion = 2 requests per session

Peak Load:
- 400 students allocate within 60 seconds
- 400 requests / 60 seconds = 6.67 RPS average
- Actual burst: 100-150 concurrent (sub-second spike)

Current Issue:
- During testing with 150 concurrent students, 25% get 429 errors
- Retries succeed, but adds 2-3 second delay

Expected Impact:
- 500 burst would handle 400 students with 25% safety margin
- 100 RPS sustained handles back-to-back events
```

### How Limits Are Changed

**Process:**
1. Update `app/main.py` line 93
2. Build new Docker image
3. Deploy to ECS (new task definition revision)
4. Verify with load test

**Example Change:**
```python
# Before
app.add_middleware(RateLimitMiddleware, requests_per_second=50, burst=200)

# After
app.add_middleware(RateLimitMiddleware, requests_per_second=100, burst=500)
```

---

## Technical Implementation

### Rate Limit Middleware

**File:** `app/middleware/rate_limit.py`

**Key Components:**

```python
class RateLimitMiddleware:
    def __init__(self, app, requests_per_second: int, burst: int):
        self.rps = requests_per_second
        self.burst = burst
        self.buckets = {}  # Per-IP buckets

    async def __call__(self, request: Request, call_next):
        client_ip = self._get_client_ip(request)

        # Get or create bucket for this IP
        bucket = self.buckets.get(client_ip)
        if not bucket:
            bucket = TokenBucket(self.rps, self.burst)
            self.buckets[client_ip] = bucket

        # Try to consume token
        if not bucket.consume():
            return rate_limit_response(bucket.time_until_refill())

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.burst)
        response.headers["X-RateLimit-Remaining"] = str(bucket.tokens)
        response.headers["X-RateLimit-Reset"] = str(bucket.reset_time)

        return response
```

**Token Bucket Algorithm:**
```python
class TokenBucket:
    def __init__(self, rate: float, capacity: int):
        self.rate = rate          # Tokens per second
        self.capacity = capacity  # Maximum tokens
        self.tokens = capacity    # Current tokens
        self.last_update = time.time()

    def consume(self, tokens: int = 1) -> bool:
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_update

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now
```

### Client IP Extraction

**File:** `app/middleware/rate_limit.py`

```python
def _get_client_ip(self, request: Request) -> str:
    """
    Extract client IP from X-Forwarded-For header (set by ALB).
    Falls back to request.client.host if header is missing.
    """
    forwarded = request.headers.get("X-Forwarded-For")

    if forwarded:
        # X-Forwarded-For: client, proxy1, proxy2
        # First IP is original client
        return forwarded.split(",")[0].strip()

    # Fallback (should not happen in production with ALB)
    return request.client.host if request.client else "unknown"
```

### WAF Configuration

**Terraform:** `terraform/waf.tf`

```hcl
resource "aws_wafv2_web_acl" "main" {
  name  = "sandbox-broker-waf"
  scope = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "RateLimitRule"
    priority = 1

    action {
      block {}
    }

    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitRule"
      sampled_requests_enabled   = true
    }
  }
}
```

### DynamoDB Auto-Scaling

**On-Demand Mode** (no manual scaling configuration required):
```hcl
resource "aws_dynamodb_table" "sandbox_pool" {
  name         = "sandbox-broker-pool"
  billing_mode = "PAY_PER_REQUEST"  # On-Demand

  # Auto-scales from 0 to 40,000 WCU/RCU
  # No throttling up to 2x previous peak load
}
```

---

## Summary

### Key Limits at a Glance

| Layer | Limit | Scope | Response |
|-------|-------|-------|----------|
| **WAF** | 2000 req / 5 min | Per IP | 403 Forbidden |
| **App Rate Limit** | 50 RPS sustained | Per IP | 429 Too Many Requests |
| **App Burst** | 200 concurrent | Per IP | 429 Too Many Requests |
| **DynamoDB** | 40,000 WCU/RCU | Table | 500 Internal Error (rare) |
| **ALB** | 10,000 conn/sec | Load balancer | Connection refused (very rare) |
| **ECS** | 2-10 tasks | Auto-scaling | Slow response (temp) |

### Recommended Client Behavior

**Best Practices:**
1. ✅ **Implement exponential backoff** for 429 errors
2. ✅ **Monitor rate limit headers** (`X-RateLimit-Remaining`)
3. ✅ **Cache responses** when possible (avoid repeated GET requests)
4. ✅ **Handle 403 as WAF block** (wait 5 minutes or use different IP)
5. ✅ **Use unique sandbox IDs** per student (enables idempotency)

**Anti-Patterns:**
1. ❌ **Polling endpoints** (use webhooks if possible)
2. ❌ **No retry logic** (network blips happen)
3. ❌ **Infinite retries** (respect 429 and back off)
4. ❌ **Ignoring rate limit headers** (proactive throttling better than errors)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-06
**API Version:** 1.3.0
**Owner:** Igor Racic
