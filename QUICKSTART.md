# Quick Start Guide

## Local Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (for local DynamoDB)

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone and navigate to project
cd Sandbox-API-Broker

# 2. Start services (DynamoDB Local + API)
docker-compose up -d

# 3. Setup test data
docker-compose exec api python scripts/setup_local_db.py

# 4. Visit API docs
open http://localhost:8080/v1/docs
```

### Option 2: Local Python Development

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start DynamoDB Local (separate terminal)
docker run -p 8000:8000 amazon/dynamodb-local

# 4. Copy environment config
cp .env.example .env

# 5. Setup database and seed data
python scripts/setup_local_db.py

# 6. Run the API
uvicorn app.main:app --reload --port 8080

# 7. Visit API docs
open http://localhost:8080/v1/docs
```

## Testing the API

### 1. Allocate a Sandbox

```bash
curl -X POST http://localhost:8080/v1/allocate \
  -H "Authorization: Bearer dev_token_local" \
  -H "X-Track-ID: test-track-123" \
  -H "Content-Type: application/json"
```

**Expected Response (201 Created):**
```json
{
  "sandbox_id": "abc-123-def",
  "name": "test-sandbox-1",
  "external_id": "ext-xyz",
  "allocated_at": 1234567890,
  "expires_at": 1234582290
}
```

### 2. Get Sandbox Details

```bash
curl -X GET http://localhost:8080/v1/sandboxes/{sandbox_id} \
  -H "Authorization: Bearer dev_token_local" \
  -H "X-Track-ID: test-track-123"
```

### 3. Mark for Deletion

```bash
curl -X POST http://localhost:8080/v1/sandboxes/{sandbox_id}/mark-for-deletion \
  -H "Authorization: Bearer dev_token_local" \
  -H "X-Track-ID: test-track-123"
```

**Expected Response (200 OK):**
```json
{
  "sandbox_id": "abc-123-def",
  "status": "pending_deletion",
  "deletion_requested_at": 1234567900
}
```

### 4. Test Idempotency

```bash
# Same track requests allocation twice - should return same sandbox
curl -X POST http://localhost:8080/v1/allocate \
  -H "Authorization: Bearer dev_token_local" \
  -H "X-Track-ID: test-track-123"

# Returns 200 OK with same sandbox (not 201)
```

## Running Tests

```bash
# Run unit tests
pytest tests/unit -v

# Run with coverage
pytest tests/unit --cov=app --cov-report=html

# View coverage report
open htmlcov/index.html
```

## Verify Setup

1. **Health Check:**
   ```bash
   curl http://localhost:8080/healthz
   # {"status": "healthy"}
   ```

2. **API Docs:**
   - Swagger UI: http://localhost:8080/v1/docs
   - ReDoc: http://localhost:8080/v1/redoc

3. **Check DynamoDB Local:**
   ```bash
   aws dynamodb list-tables --endpoint-url http://localhost:8000
   # Should show: SandboxPool
   ```

## Environment Variables

Key settings in `.env`:

```bash
# Tokens (change for production!)
BROKER_API_TOKEN=dev_token_local
BROKER_ADMIN_TOKEN=admin_token_local

# DynamoDB (local)
DDB_ENDPOINT_URL=http://localhost:8000
DDB_TABLE_NAME=SandboxPool

# Behavior
LAB_DURATION_HOURS=4
K_CANDIDATES=15
```

## Troubleshooting

### DynamoDB Connection Error
```bash
# Ensure DynamoDB Local is running
docker ps | grep dynamodb
# Should show running container

# Test connectivity
aws dynamodb list-tables --endpoint-url http://localhost:8000
```

### Import Errors
```bash
# Reinstall dependencies
pip install -r requirements.txt

# Or use Docker
docker-compose down && docker-compose up --build
```

### No Sandboxes Available
```bash
# Re-seed test data
python scripts/setup_local_db.py
```

## Next Steps

1. ✅ Local dev working → Proceed to **Phase 2: Admin Endpoints**
2. Add sync job to pull from ENG CSP
3. Add cleanup job for pending_deletion
4. Deploy to AWS (ECS + DynamoDB)

---

**Need help?** Check `PROJECT_SUMMARY.md` for architecture details.
