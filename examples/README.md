# Instruqt Integration Examples

This folder contains example scripts for integrating the Sandbox Broker API with Instruqt tracks.

## Overview

Instead of creating sandboxes directly in CSP (slow, ~2-3 minutes), these scripts **allocate pre-created sandboxes** from the broker pool (fast, <100ms).

**Benefits:**
- ⚡ Instant allocation (<100ms vs 2-3 minutes)
- 🔒 Zero double-allocations (atomic DynamoDB operations)
- 🔄 Automatic cleanup (background jobs)
- 🛡️ Safety net (auto-expiry after 4.5 hours)
- 📊 Multi-student support (same lab, different sandboxes)

---

## Files

### 1. `instruqt_broker_allocation.py`
Allocates a sandbox from the broker pool when a student starts a lab.

**Usage in Instruqt:**
```bash
# In your track's setup lifecycle hook
python3 instruqt_broker_allocation.py
```

**Environment Variables:**
- `BROKER_API_TOKEN` (required) - Your broker API token
- `INSTRUQT_PARTICIPANT_ID` (auto) - Unique per student, provided by Instruqt
- `INSTRUQT_TRACK_SLUG` (auto) - Lab identifier, provided by Instruqt (saved as `track_name` for analytics)
- `SANDBOX_NAME_PREFIX` (optional) - Filter sandboxes by name prefix (e.g., "lab-adventure")
- `BROKER_API_URL` (optional) - Default: production URL

> **Note:** The lab identifier (`INSTRUQT_TRACK_SLUG`) is optional but recommended - it's saved to the broker for analytics and allows you to query "which sandboxes are allocated to lab X".

> **New Feature:** Use `SANDBOX_NAME_PREFIX` to filter which sandboxes can be allocated. For example, set `SANDBOX_NAME_PREFIX=lab-adventure` to only allocate sandboxes whose names start with "lab-adventure". This allows multiple labs to share the same sandbox pool while each lab uses a specific subset.

**Output Files:**
- `sandbox_id.txt` - Broker's internal sandbox ID
- `external_id.txt` - CSP UUID (use this to connect to the sandbox)
- `sandbox_name.txt` - CSP sandbox/tenant name (e.g., "test-3")

---

### 2. `instruqt_broker_cleanup.py`
Marks a sandbox for deletion when a student stops the lab.

**Usage in Instruqt:**
```bash
# In your track's cleanup lifecycle hook
python3 instruqt_broker_cleanup.py
```

**What it does:**
- Marks sandbox as `pending_deletion` in broker
- Background cleanup job deletes from CSP within ~5 minutes
- If student doesn't stop, auto-expiry cleans up after 4.5 hours

---

## Integration Guide

### Step 1: Set Up Broker Token

Add the broker API token as an Instruqt environment variable:

```bash
# In Instruqt track config
BROKER_API_TOKEN=<your_token_here>
```

Get your token from AWS Secrets Manager:
```bash
aws secretsmanager get-secret-value \
  --secret-id sandbox-broker-broker-api-token-* \
  --region eu-central-1 \
  --query SecretString \
  --output text
```

---

### Step 2: Sync Sandboxes to Broker

Before using the broker, you need to seed sandboxes from your CSP tenant.

**Option A: Manual Sync (Admin API)**
```bash
curl -X POST https://api-sandbox-broker.highvelocitynetworking.com/v1/admin/sync \
  -H "Authorization: Bearer <ADMIN_TOKEN>"
```

**Option B: Automatic Sync (Background Job)**
- Runs every 10 minutes automatically
- Pulls new sandboxes from CSP
- Marks deleted sandboxes as stale

---

### Step 3: Add Scripts to Your Instruqt Track

1. **Copy scripts to your track repository**
   ```bash
   cp instruqt_broker_*.py /path/to/your/instruqt/track/
   ```

2. **Update track's setup lifecycle hook**
   ```bash
   #!/bin/bash
   # Setup script (runs when student starts lab)

   python3 instruqt_broker_allocation.py

   # Export variables from files for later use
   export STUDENT_TENANT=$(cat sandbox_name.txt)
   export CSP_ACCOUNT_ID=$(cat external_id.txt)
   export SANDBOX_ID=$(cat sandbox_id.txt)

   # Or use Instruqt's set-var to persist across steps
   set-var STUDENT_TENANT $(cat sandbox_name.txt)
   set-var CSP_ACCOUNT_ID $(cat external_id.txt)

   # Now connect to CSP using these variables
   # ... your CSP connection logic here ...
   ```

3. **Update track's cleanup lifecycle hook**
   ```bash
   #!/bin/bash
   # Cleanup script (runs when student stops lab)

   python3 instruqt_broker_cleanup.py
   ```

---

### Step 4: Use External ID in Your Track

The `external_id.txt` file contains the CSP UUID needed to connect to the sandbox.

**Example: Connect to BloxOne DDI API**
```bash
EXTERNAL_ID=$(cat external_id.txt)

curl https://csp.infoblox.com/api/ddi/v1/ipam/address \
  -H "Authorization: Token ${INFOBLOX_TOKEN}" \
  -H "X-Account-ID: ${EXTERNAL_ID}"
```

---

## API Response Format

### Allocation Response (201 Created)
```json
{
  "sandbox_id": "2012224",
  "name": "sandbox-1",
  "external_id": "af06cbf7-b07c-4c4f-bfa4-bd7dd0e2d4c3",
  "allocated_at": 1728054123,
  "expires_at": 1728070323
}
```

**Fields:**
- `sandbox_id`: Broker's internal ID
- `name`: Human-readable name
- `external_id`: **CSP UUID (use this to connect to CSP APIs)**
- `allocated_at`: Unix timestamp when allocated
- `expires_at`: Unix timestamp when allocation expires (4 hours)

### Idempotent Response (200 OK)
If the same student makes multiple allocation requests, they get the **same sandbox back** (idempotent).

### Pool Exhausted (409 Conflict)
```json
{
  "detail": {
    "code": "POOL_EXHAUSTED",
    "message": "No available sandboxes in pool"
  }
}
```

**What to do:**
- Contact admin to provision more sandboxes in CSP
- Or wait for students to finish their labs

---

## Troubleshooting

### Error: "BROKER_API_TOKEN environment variable not set"
- Add `BROKER_API_TOKEN` to your Instruqt track environment variables
- Get token from AWS Secrets Manager (see Step 1)

### Error: "Pool exhausted: No sandboxes available"
- Check pool stats: `GET /v1/admin/stats`
- Sync more sandboxes from CSP: `POST /v1/admin/sync`
- Or create more sandboxes in your CSP tenant

### Error: "Rate limited by WAF"
- Normal if many students start labs simultaneously
- Script will retry automatically
- WAF limit: 2000 requests per 5 minutes per IP

### Sandbox not cleaned up
- Background cleanup runs every 5 minutes
- Check CloudWatch logs: `/ecs/sandbox-broker`
- Manual cleanup: `POST /v1/admin/cleanup`

### Multiple students get same sandbox
- **This should never happen** (zero double-allocations guaranteed)
- If it does, check:
  - Each student has unique `INSTRUQT_PARTICIPANT_ID`
  - You're using `X-Instruqt-Sandbox-ID` header (not `X-Track-ID` with lab name)
  - DynamoDB atomic operations are working

---

## Testing

### Quick Test (Automated Script)

The fastest way to test the allocation:

```bash
# Get your API token from AWS Secrets Manager
export BROKER_API_TOKEN=$(aws secretsmanager get-secret-value \
  --secret-id sandbox-broker-broker-api-token-20251004124001695200000001 \
  --region eu-central-1 --profile okta-sso \
  --query SecretString --output text)

# Run the test script
./test_allocation.sh
```

**What it does:**
1. Simulates Instruqt environment (generates test student ID)
2. Calls the allocation API
3. Shows all generated files and their contents
4. Provides cleanup command

**Output files created:**
- `sandbox_id.txt` - Broker's internal sandbox ID (2012244)
- `external_id.txt` - CSP UUID to connect to the sandbox (8ce6e4ed-ec1f-40f4-8340-91f20f4d26aa)
- `sandbox_name.txt` - CSP tenant name (yfu3kuhgesdm)
- `sandbox_env.sh` - Sourceable shell script with env vars

### Manual Test - Allocation
```bash
export BROKER_API_TOKEN="<your_token>"
export INSTRUQT_PARTICIPANT_ID="test-student-123"
export INSTRUQT_TRACK_SLUG="test-lab"

python3 instruqt_broker_allocation.py

# View the allocated sandbox details
cat sandbox_id.txt      # Broker ID: 2012244
cat external_id.txt     # CSP UUID: 8ce6e4ed-ec1f-40f4-8340-91f20f4d26aa
cat sandbox_name.txt    # Tenant name: yfu3kuhgesdm

# Or source the env vars
source sandbox_env.sh
echo $CSP_ACCOUNT_ID    # 8ce6e4ed-ec1f-40f4-8340-91f20f4d26aa
echo $STUDENT_TENANT    # yfu3kuhgesdm
```

### Manual Test - Cleanup
```bash
export BROKER_API_TOKEN="<your_token>"
export INSTRUQT_PARTICIPANT_ID="test-student-123"

# After allocation creates sandbox_id.txt
python3 instruqt_broker_cleanup.py
```

---

## Sandbox Name Filtering

The broker supports **optional name prefix filtering** to allow different labs to use different subsets of the sandbox pool.

### How It Works

When you set the `SANDBOX_NAME_PREFIX` environment variable, the broker will only allocate sandboxes whose names start with that prefix.

**Example Scenario:**
- **Sandbox Pool**: Contains `sandbox-1`, `sandbox-2`, `lab-adventure-100`, `lab-adventure-101`, `lab-security-50`, `lab-security-51`
- **Lab A** (Adventure Lab): Sets `SANDBOX_NAME_PREFIX=lab-adventure`
  - Students in Lab A will ONLY get sandboxes: `lab-adventure-100`, `lab-adventure-101`
- **Lab B** (Security Lab): Sets `SANDBOX_NAME_PREFIX=lab-security`
  - Students in Lab B will ONLY get sandboxes: `lab-security-50`, `lab-security-51`
- **Lab C** (General Lab): No prefix set
  - Students in Lab C can get ANY available sandbox

### Usage in Instruqt

Add the environment variable to your track configuration:

```bash
# In Instruqt track environment variables
SANDBOX_NAME_PREFIX=lab-adventure
```

The allocation script will automatically send this as the `X-Sandbox-Name-Prefix` header to the broker.

### Benefits

- ✅ **One sandbox pool, multiple labs** - No need to create separate tenants or brokers
- ✅ **Server-side filtering** - Efficient, no wasted allocations
- ✅ **Flexible naming** - Supports any prefix pattern (e.g., `lab-adventure`, `start-lab-adventure`, `prod-`)
- ✅ **Backward compatible** - Labs without prefix can still use all sandboxes

---

## Multi-Student Support

The broker supports **multiple students running the same lab simultaneously**.

**How it works:**
- Each student gets unique `INSTRUQT_PARTICIPANT_ID` from Instruqt
- This is sent as `X-Instruqt-Sandbox-ID` header to broker
- Each student gets a **different sandbox** from the pool
- All students can share same `INSTRUQT_TRACK_SLUG` (lab identifier)

**Example:**
- Student 1 (ID: `inst-student-1-abc`) → Sandbox A
- Student 2 (ID: `inst-student-2-def`) → Sandbox B
- Student 3 (ID: `inst-student-3-ghi`) → Sandbox C
- All in same lab: `aws-security-101` ✅

---

## Production URLs

- **Broker API**: https://api-sandbox-broker.highvelocitynetworking.com/v1
- **Swagger Docs**: https://api-sandbox-broker.highvelocitynetworking.com/v1/docs
- **Health Check**: https://api-sandbox-broker.highvelocitynetworking.com/healthz
- **Metrics**: https://api-sandbox-broker.highvelocitynetworking.com/metrics

---

## Support

For issues or questions:
1. Check CloudWatch logs: `/ecs/sandbox-broker`
2. Check pool stats: `GET /v1/admin/stats`
3. Review docs: https://github.com/iracic82/Sandbox-API-Broker

---

**Version**: 1.1.0 (Multi-Student Support)
**Last Updated**: 2025-10-05
