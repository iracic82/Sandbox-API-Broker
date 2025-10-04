# Testing with Real ENG CSP API - Step by Step Guide

This guide shows you exactly how to test the Sandbox Broker with your real ENG CSP tenant.

---

## Prerequisites

1. **Your ENG CSP API Token**
   - You should have this from Infoblox CSP
   - It looks like: `Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...` (just the token part, not the "Bearer " prefix)

2. **Access to your ENG tenant**
   - You should have sandbox accounts in your tenant
   - Based on your earlier example, you have accounts like:
     - "Infoblox TME On-Demand lab" (parent account)
     - "My Sandbox Account" (sandbox)
     - "testing-igor" (sandbox)

---

## Option 1: Quick Test (Recommended for First Time)

### Step 1: Test Your Token Directly

First, let's verify your token works with the CSP API:

```bash
# Replace YOUR_TOKEN_HERE with your actual token
export CSP_API_TOKEN="YOUR_TOKEN_HERE"

# Test the API directly
curl -H "Authorization: Bearer $CSP_API_TOKEN" \
  "https://csp.infoblox.com/v2/current_user/accounts" | jq .
```

**Expected Output**: JSON with your accounts, including:
```json
{
  "results": [
    {
      "account_type": "sandbox",
      "state": "active",
      "id": "identity/accounts/...",
      "name": "testing-igor",
      "csp_id": 2012133
    }
  ]
}
```

**If this fails**, check:
- ❌ Token is expired
- ❌ Token doesn't have correct permissions
- ❌ Network connectivity to csp.infoblox.com

### Step 2: Count Your Active Sandboxes

```bash
# How many active sandbox accounts do you have?
curl -s -H "Authorization: Bearer $CSP_API_TOKEN" \
  "https://csp.infoblox.com/v2/current_user/accounts" | \
  jq '[.results[] | select(.account_type=="sandbox" and .state=="active")] | length'
```

**Remember this number** - the broker should sync this many sandboxes.

### Step 3: Run the Automated Test Script

```bash
# Make the script executable
chmod +x scripts/test_real_csp_api.sh

# Run it (it will use your $CSP_API_TOKEN from above)
bash scripts/test_real_csp_api.sh
```

**What the script does**:
1. ✅ Tests your token against CSP API directly
2. ✅ Updates the .env file with your real token
3. ✅ Restarts the Docker container
4. ✅ Triggers a manual sync
5. ✅ Compares sandbox counts (CSP vs Broker)
6. ✅ Shows you the results

**Expected Output**:
```
========================================
ENG CSP Real API Integration Test
========================================
✅ CSP_API_TOKEN is set

=== Test 1: Direct CSP API Call ===
✅ API call successful (HTTP 200)
   Total accounts: 3
   Sandbox accounts: 2
   Active sandboxes: 2

=== Test 5: Trigger Manual Sync ===
✅ Sync successful (HTTP 200)
{
  "status": "completed",
  "synced": 2,
  "marked_stale": 0,
  "duration_ms": 156
}
```

---

## Option 2: Manual Step-by-Step (If You Want Control)

### Step 1: Update .env File

Open `.env` file and replace the placeholder:

```bash
# Before:
CSP_API_TOKEN=your_csp_token_here

# After:
CSP_API_TOKEN=eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...  # Your actual token
```

### Step 2: Restart Docker Containers

```bash
# Stop everything
docker compose down

# Start fresh
docker compose up -d

# Wait for services to start
sleep 5
```

### Step 3: Check the Logs

```bash
# Look for production mode indicator
docker logs sandbox-broker-api 2>&1 | grep "ENG CSP"
```

**If using MOCK mode**, you'll see:
```
[ENG CSP] Using MOCK data (set CSP_API_TOKEN to use real API)
[ENG CSP] MOCK: Deleting sandbox ext-eng-1
```

**If using PRODUCTION mode**, you'll see:
```
[ENG CSP] Fetched 2 active sandbox accounts
[ENG CSP] Deleted sandbox identity/accounts/... (status: 200)
```

### Step 4: Initialize the Database

```bash
# Create table and seed initial data
docker cp init_and_seed.py sandbox-broker-api:/app/
docker exec sandbox-broker-api python /app/init_and_seed.py
```

### Step 5: Trigger a Manual Sync

```bash
# Call the sync endpoint
curl -X POST \
  -H "Authorization: Bearer admin_token_local" \
  http://localhost:8080/v1/admin/sync | jq .
```

**Expected Response**:
```json
{
  "status": "completed",
  "synced": 2,
  "marked_stale": 6,
  "duration_ms": 234
}
```

**What this means**:
- `synced: 2` - Fetched 2 sandboxes from your ENG CSP tenant
- `marked_stale: 6` - The 6 test sandboxes (avail-1, etc.) are marked stale (not in CSP)

### Step 6: List Sandboxes in the Broker

```bash
# See what's in the broker now
curl -H "Authorization: Bearer admin_token_local" \
  "http://localhost:8080/v1/admin/sandboxes" | jq .
```

**Expected**: You should see your real sandbox accounts:
```json
{
  "sandboxes": [
    {
      "sandbox_id": "2012133",
      "name": "testing-igor",
      "external_id": "identity/accounts/7744b13b-8127-4d2b-8c3b-c74c806df57e",
      "status": "available"
    }
  ]
}
```

### Step 7: Check the Sync Logs

```bash
# Look for detailed sync logs
docker logs sandbox-broker-api 2>&1 | grep -A 5 "Fetched.*sandbox"
```

You should see:
```
[ENG CSP] Fetched 2 active sandbox accounts
```

---

## What to Expect

### Successful Integration

**Logs**:
```
[ENG CSP] Fetched 2 active sandbox accounts
[sync_job] Running sync...
{"message": "Synced 2 sandboxes, marked 6 as stale", "outcome": "success"}
```

**Sandbox List**:
- Your real sandboxes appear with their actual names from CSP
- `sandbox_id` = CSP's `csp_id` (e.g., 2012133)
- `external_id` = Full identity path (e.g., "identity/accounts/...")
- `status` = "available" (ready for allocation)

**Metrics**:
```bash
curl http://localhost:8080/metrics | grep broker_sync
```
You should see:
```
broker_sync_total{outcome="success"} 1.0
broker_sync_sandboxes_synced_total 2.0
```

### Still in Mock Mode (Something Wrong)

**Logs**:
```
[ENG CSP] Using MOCK data (set CSP_API_TOKEN to use real API)
[ENG CSP] MOCK: Deleting sandbox ext-eng-1
```

**Troubleshooting**:
1. Check .env file: `cat .env | grep CSP_API_TOKEN`
2. Restart completely: `docker compose down && docker compose up -d`
3. Check environment in container: `docker exec sandbox-broker-api env | grep CSP`

---

## Verifying End-to-End

### Test 1: Allocate a Real Sandbox

```bash
# Allocate one of your real sandboxes
curl -X POST \
  -H "Authorization: Bearer your_track_token_here" \
  -H "X-Track-ID: test-track-123" \
  http://localhost:8080/v1/allocate | jq .
```

**Expected**:
```json
{
  "sandbox_id": "2012133",
  "name": "testing-igor",
  "external_id": "identity/accounts/7744b13b-...",
  "status": "allocated",
  "allocated_at": 1759575000,
  "expires_at": 1759589400
}
```

### Test 2: Mark for Deletion

```bash
# Mark it for deletion
curl -X POST \
  -H "Authorization: Bearer your_track_token_here" \
  -H "X-Track-ID: test-track-123" \
  http://localhost:8080/v1/sandboxes/2012133/mark-for-deletion | jq .
```

**Expected**:
```json
{
  "sandbox_id": "2012133",
  "status": "pending_deletion",
  "deletion_requested_at": 1759575100
}
```

### Test 3: Trigger Cleanup (Will Delete from Real CSP!)

**⚠️ WARNING**: This will actually DELETE the sandbox from your ENG CSP tenant!

```bash
# Only run this if you're okay with deleting the sandbox
curl -X POST \
  -H "Authorization: Bearer admin_token_local" \
  http://localhost:8080/v1/admin/cleanup | jq .
```

**Expected**:
```json
{
  "status": "completed",
  "deleted": 1,
  "failed": 0,
  "duration_ms": 456
}
```

**Logs**:
```
[ENG CSP] Deleted sandbox identity/accounts/7744b13b-... (status: 200)
```

**Verify in CSP Portal**: The sandbox should be gone from your ENG tenant.

---

## Monitoring Production Mode

### Check Circuit Breaker Status

```bash
# If you get many errors, circuit breaker will open
docker logs sandbox-broker-api 2>&1 | grep CircuitBreaker
```

**Normal operation**: No circuit breaker messages

**CSP API down**: You'll see:
```
[CircuitBreaker:eng_csp] Failure threshold reached (5/5), opening circuit
[CircuitBreaker:eng_csp] Circuit breaker is OPEN
```

### Check Sync Success Rate

```bash
curl -s http://localhost:8080/metrics | grep broker_sync_total
```

**Healthy**:
```
broker_sync_total{outcome="success"} 10.0
broker_sync_total{outcome="error"} 0.0
```

**Having issues**:
```
broker_sync_total{outcome="success"} 2.0
broker_sync_total{outcome="error"} 8.0  # Circuit breaker likely open
```

---

## Reverting to Mock Mode

When done testing:

```bash
# Option 1: Restore from backup
cp .env.backup .env
docker compose restart api

# Option 2: Manually edit .env
# Change CSP_API_TOKEN back to: your_csp_token_here
docker compose restart api

# Verify mock mode
docker logs sandbox-broker-api 2>&1 | grep "Using MOCK"
```

---

## Common Issues

### Issue 1: "401 Unauthorized"

**Cause**: Invalid or expired token

**Fix**:
```bash
# Test token manually
curl -I -H "Authorization: Bearer $CSP_API_TOKEN" \
  https://csp.infoblox.com/v2/current_user/accounts
```

### Issue 2: "Synced 0 sandboxes"

**Cause**: No active sandbox accounts in your tenant

**Check**:
```bash
curl -H "Authorization: Bearer $CSP_API_TOKEN" \
  "https://csp.infoblox.com/v2/current_user/accounts" | \
  jq '[.results[] | select(.account_type=="sandbox" and .state=="active")]'
```

### Issue 3: Still seeing mock logs

**Cause**: Token not updated or container didn't restart

**Fix**:
```bash
# Complete restart
docker compose down
docker compose up -d --build

# Check environment
docker exec sandbox-broker-api env | grep CSP_API_TOKEN
```

---

## Summary

**Quick Test**:
```bash
export CSP_API_TOKEN="your-real-token"
bash scripts/test_real_csp_api.sh
```

**Manual Test**:
1. Update .env with real token
2. `docker compose down && docker compose up -d`
3. `curl -X POST -H "Authorization: Bearer admin_token_local" http://localhost:8080/v1/admin/sync`
4. Check logs: `docker logs sandbox-broker-api | grep "ENG CSP"`

**Success Indicators**:
- ✅ Logs show: `[ENG CSP] Fetched X active sandbox accounts`
- ✅ Sync returns: `"synced": X` (matching your CSP sandbox count)
- ✅ Sandboxes list shows your real CSP sandboxes with actual names

**Need Help?**
- Check ENG_CSP_INTEGRATION.md for detailed troubleshooting
- Review logs: `docker logs sandbox-broker-api`
- Check metrics: `curl http://localhost:8080/metrics | grep broker_sync`
