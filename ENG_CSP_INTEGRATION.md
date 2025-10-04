# ENG CSP API Integration Guide

This document explains how to integrate the Sandbox Broker with the real ENG CSP API.

---

## Overview

The Sandbox Broker can operate in two modes:
1. **Mock Mode** (default for development)
2. **Production Mode** (requires valid CSP API token)

---

## Mock Mode (Default)

When `CSP_API_TOKEN` is not configured or set to the placeholder value, the service uses mock data.

**Indicators**:
- Log message: `[ENG CSP] Using MOCK data (set CSP_API_TOKEN to use real API)`
- Returns 5 hardcoded sandbox entries
- All operations succeed immediately

**Configuration**:
```bash
# .env file
CSP_API_TOKEN=your_csp_token_here  # Placeholder triggers mock mode
CSP_BASE_URL=https://csp.infoblox.com/v2
```

---

## Production Mode

### Prerequisites

1. **ENG CSP API Token**
   - Obtain a valid API token from Infoblox CSP
   - Token should have permissions to:
     - List accounts (`GET /v2/current_user/accounts`)
     - Delete accounts (`DELETE /v2/identity/accounts/{id}`)

2. **Parent Account Access**
   - Your token must have access to the parent ENG tenant account
   - Sandboxes must be pre-created under this parent account

### Configuration

Update your `.env` file or environment variables:

```bash
# ENG CSP Integration
CSP_BASE_URL=https://csp.infoblox.com/v2
CSP_API_TOKEN=<your-actual-token-here>  # Replace with real token
CSP_TIMEOUT_CONNECT_SEC=2
CSP_TIMEOUT_READ_SEC=5

# Circuit Breaker (protects against CSP API failures)
CIRCUIT_BREAKER_THRESHOLD=5  # Open circuit after 5 failures
CIRCUIT_BREAKER_TIMEOUT_SEC=60  # Wait 60s before retry
```

### Activation

The service automatically switches to production mode when:
- `CSP_API_TOKEN` is set to a value **other than** `your_csp_token_here`
- `CSP_BASE_URL` is configured

**Log message**: `[ENG CSP] Fetched {count} active sandbox accounts`

---

## API Endpoints Used

### 1. List Sandboxes

**Endpoint**: `GET /v2/current_user/accounts`

**Request**:
```http
GET https://csp.infoblox.com/v2/current_user/accounts
Authorization: Bearer <token>
```

**Response Format** (based on your example):
```json
{
  "results": [
    {
      "account_type": "sandbox",
      "state": "active",
      "id": "identity/accounts/75c15573-6565-4116-825e-d91d08a3fb2a",
      "name": "My Sandbox Account",
      "csp_id": 2009521,
      "created_at": "2025-03-27T16:53:47.605459Z",
      "parent_account_id": "identity/ea5059b0-46dd-4ea6-87df-c326485e1111"
    }
  ]
}
```

**Filtering**:
- Only accounts where `account_type == "sandbox"`
- Only accounts where `state == "active"`

**Field Mapping**:
| CSP API Field | Broker Field | Notes |
|---------------|--------------|-------|
| `csp_id` | `sandbox_id` | Numeric ID used as primary key |
| `name` | `name` | Sandbox display name |
| `id` | `external_id` | Full identity path for deletion |
| `created_at` | `created_at` | Parsed from ISO 8601 to Unix timestamp |

### 2. Delete Sandbox

**Endpoint**: `DELETE /v2/{external_id}`

**Request**:
```http
DELETE https://csp.infoblox.com/v2/identity/accounts/75c15573-6565-4116-825e-d91d08a3fb2a
Authorization: Bearer <token>
```

**Success Codes**:
- `200 OK` - Deleted successfully
- `204 No Content` - Deleted successfully
- `404 Not Found` - Already deleted (treated as success)

**Failure Handling**:
- On failure, sandbox marked as `deletion_failed` in DynamoDB
- Retry count incremented
- Background cleanup job retries on next run

### 3. Create Sandbox (Not Implemented)

**Status**: Not implemented for production

**Reason**: Sandboxes should be pre-created in the ENG CSP tenant.

**Mock Behavior**: Returns a UUID-based mock sandbox in mock mode.

---

## Circuit Breaker Protection

All ENG CSP API calls are protected by a circuit breaker.

### States

1. **CLOSED** (Normal)
   - All requests pass through
   - Failures increment counter

2. **OPEN** (Failing)
   - Requests rejected immediately with `CircuitBreakerError`
   - Prevents overwhelming a failing API
   - Lasts for `CIRCUIT_BREAKER_TIMEOUT_SEC` (default: 60s)

3. **HALF_OPEN** (Testing Recovery)
   - One request allowed through to test if service recovered
   - Success → CLOSED
   - Failure → OPEN again

### Configuration

```bash
CIRCUIT_BREAKER_THRESHOLD=5  # Failures before opening circuit
CIRCUIT_BREAKER_TIMEOUT_SEC=60  # Seconds before attempting reset
```

### Monitoring

**Log Messages**:
- `[CircuitBreaker:eng_csp] Attempting reset (HALF_OPEN)`
- `[CircuitBreaker:eng_csp] Service recovered, closing circuit`
- `[CircuitBreaker:eng_csp] Failure threshold reached (5/5), opening circuit`
- `[CircuitBreaker:eng_csp] Recovery failed, opening circuit again`

**Metrics**:
- `broker_sync_total{outcome="error"}` - Incremented on sync failures
- Check circuit state via logs or add custom metrics

---

## Sync Job Behavior

The background sync job runs every `SYNC_INTERVAL_SEC` (default: 600s = 10 minutes).

### Logic

1. **Fetch** all active sandboxes from ENG CSP
2. **Upsert** each sandbox to DynamoDB as `available` (if not already allocated)
3. **Preserve** allocated and pending_deletion sandboxes
4. **Mark** missing sandboxes as `stale` (no longer in ENG tenant)

### Production vs Mock

**Mock Mode**:
- Returns 5 hardcoded sandboxes
- Marks 2 existing sandboxes as stale (if they don't match mock IDs)

**Production Mode**:
- Fetches real sandboxes from CSP API
- Syncs actual tenant state to DynamoDB
- Marks removed sandboxes as stale

---

## Error Handling

### API Failures

| Error | Behavior | Recovery |
|-------|----------|----------|
| Network timeout | Circuit breaker opens after threshold | Auto-retry after timeout |
| 401 Unauthorized | Circuit breaker opens, logs error | Fix token, wait for circuit reset |
| 429 Rate Limit | Circuit breaker opens | CSP API rate limits enforced |
| 500 Server Error | Circuit breaker opens | Wait for CSP recovery |
| Connection refused | Circuit breaker opens | Check CSP_BASE_URL |

### Cleanup Failures

When delete fails:
1. Sandbox marked as `deletion_failed`
2. `deletion_retry_count` incremented
3. Cleanup job retries on next run
4. Admin can query `status=deletion_failed` to investigate

### Circuit Open Errors

When circuit breaker is open:
```
CircuitBreakerError: Circuit breaker 'eng_csp' is OPEN. Service unavailable. Retry after 45s
```

**Response**: Wait for circuit to reset (check retry_after seconds)

---

## Testing

### Test Mock Mode

```bash
# Start services (uses mock by default)
docker compose up -d

# Trigger sync job manually
curl -X POST -H "Authorization: Bearer admin_token_local" \
  http://localhost:8080/v1/admin/sync

# Check logs
docker logs sandbox-broker-api | grep "ENG CSP"
# Should see: [ENG CSP] Using MOCK data
```

### Test Production Mode

```bash
# Set real token
export CSP_API_TOKEN="your-real-token-here"

# Update .env
echo "CSP_API_TOKEN=$CSP_API_TOKEN" >> .env

# Restart services
docker compose restart api

# Trigger sync
curl -X POST -H "Authorization: Bearer admin_token_local" \
  http://localhost:8080/v1/admin/sync

# Check logs
docker logs sandbox-broker-api | grep "ENG CSP"
# Should see: [ENG CSP] Fetched X active sandbox accounts
```

### Test Circuit Breaker

```bash
# Simulate CSP API failure (set invalid token)
export CSP_API_TOKEN="invalid-token"
docker compose restart api

# Trigger sync 6 times (threshold is 5)
for i in {1..6}; do
  curl -X POST -H "Authorization: Bearer admin_token_local" \
    http://localhost:8080/v1/admin/sync
  sleep 1
done

# Check logs for circuit breaker messages
docker logs sandbox-broker-api | grep CircuitBreaker
```

---

## Production Deployment Checklist

- [ ] Obtain valid CSP API token from Infoblox
- [ ] Store token in AWS Secrets Manager (Phase 6)
- [ ] Configure `CSP_API_TOKEN` environment variable
- [ ] Verify `CSP_BASE_URL=https://csp.infoblox.com/v2`
- [ ] Test sync job manually before enabling automated runs
- [ ] Monitor circuit breaker state in production logs
- [ ] Set up alerts for `deletion_failed` status
- [ ] Configure appropriate `CIRCUIT_BREAKER_THRESHOLD` for production load
- [ ] Verify sandboxes are pre-created in ENG tenant
- [ ] Test deletion flow end-to-end

---

## Troubleshooting

### "Using MOCK data" in production

**Cause**: `CSP_API_TOKEN` still set to placeholder value

**Fix**:
```bash
# Update .env
CSP_API_TOKEN=<your-real-token>

# Restart
docker compose restart api
```

### "Circuit breaker is OPEN"

**Cause**: Too many API failures

**Fix**:
1. Check CSP API health: `curl https://csp.infoblox.com/v2/status`
2. Verify token is valid
3. Wait for circuit to reset (60 seconds)
4. Check logs for root cause

### Sync returns 0 sandboxes

**Possible Causes**:
1. No active sandbox accounts in ENG tenant
2. Token doesn't have access to parent account
3. All sandboxes are `state != "active"`

**Debug**:
```bash
# Test API directly
curl -H "Authorization: Bearer $CSP_API_TOKEN" \
  https://csp.infoblox.com/v2/current_user/accounts | jq '.results[] | select(.account_type=="sandbox")'
```

### Deletion fails repeatedly

**Cause**: Invalid external_id or API permissions

**Check**:
1. Query `deletion_failed` sandboxes: `GET /v1/admin/sandboxes?status=deletion_failed`
2. Check `deletion_retry_count`
3. Verify external_id format: `identity/accounts/{uuid}`
4. Test deletion manually via CSP API

---

## Support

For ENG CSP API issues, contact Infoblox support.

For Sandbox Broker issues, check:
- GitHub: https://github.com/iracic82/Sandbox-API-Broker
- Logs: `docker logs sandbox-broker-api`
- Metrics: http://localhost:8080/metrics
