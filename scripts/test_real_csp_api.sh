#!/bin/bash
# Test script for real ENG CSP API integration

echo "=========================================="
echo "ENG CSP Real API Integration Test"
echo "=========================================="

# Check if CSP_API_TOKEN is set
if [ -z "$CSP_API_TOKEN" ]; then
    echo "❌ ERROR: CSP_API_TOKEN environment variable not set"
    echo ""
    echo "To test with real API:"
    echo "  export CSP_API_TOKEN='your-real-token-here'"
    echo "  bash scripts/test_real_csp_api.sh"
    echo ""
    echo "Or update .env file:"
    echo "  CSP_API_TOKEN=your-real-token-here"
    echo "  docker compose restart api"
    exit 1
fi

echo "✅ CSP_API_TOKEN is set"
echo ""

# Test 1: Direct API call to verify token works
echo "=== Test 1: Direct CSP API Call ==="
echo "Testing: GET https://csp.infoblox.com/v2/current_user/accounts"
echo ""

response=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $CSP_API_TOKEN" \
    "https://csp.infoblox.com/v2/current_user/accounts")

http_code=$(echo "$response" | grep "HTTP_CODE" | cut -d: -f2)
body=$(echo "$response" | sed '/HTTP_CODE/d')

if [ "$http_code" = "200" ]; then
    echo "✅ API call successful (HTTP 200)"

    # Count total accounts
    total_accounts=$(echo "$body" | jq -r '.results | length')
    echo "   Total accounts: $total_accounts"

    # Count sandbox accounts
    sandbox_count=$(echo "$body" | jq -r '[.results[] | select(.account_type=="sandbox")] | length')
    echo "   Sandbox accounts: $sandbox_count"

    # Count active sandboxes
    active_sandboxes=$(echo "$body" | jq -r '[.results[] | select(.account_type=="sandbox" and .state=="active")] | length')
    echo "   Active sandboxes: $active_sandboxes"

    echo ""
    echo "Sample sandbox account:"
    echo "$body" | jq -r '.results[] | select(.account_type=="sandbox") | {name, csp_id, id, state, account_type} | @json' | head -1 | jq .

else
    echo "❌ API call failed (HTTP $http_code)"
    echo "Response:"
    echo "$body" | jq . 2>/dev/null || echo "$body"
    exit 1
fi

echo ""
echo "=== Test 2: Update Docker Environment ==="
echo "Updating .env file with real token..."

# Backup .env
if [ -f .env ]; then
    cp .env .env.backup
    echo "✅ Backed up .env to .env.backup"
fi

# Update or add CSP_API_TOKEN in .env
if grep -q "^CSP_API_TOKEN=" .env 2>/dev/null; then
    # Replace existing
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|^CSP_API_TOKEN=.*|CSP_API_TOKEN=$CSP_API_TOKEN|" .env
    else
        sed -i "s|^CSP_API_TOKEN=.*|CSP_API_TOKEN=$CSP_API_TOKEN|" .env
    fi
    echo "✅ Updated CSP_API_TOKEN in .env"
else
    # Add new
    echo "CSP_API_TOKEN=$CSP_API_TOKEN" >> .env
    echo "✅ Added CSP_API_TOKEN to .env"
fi

echo ""
echo "=== Test 3: Restart API Container ==="
docker compose restart api
echo "⏳ Waiting for API to start..."
sleep 5

# Wait for API to be ready
for i in {1..10}; do
    if curl -s http://localhost:8080/healthz > /dev/null 2>&1; then
        echo "✅ API is ready"
        break
    fi
    echo "   Waiting... ($i/10)"
    sleep 2
done

echo ""
echo "=== Test 4: Check API Logs for Production Mode ==="
echo "Looking for production mode indicator..."
logs=$(docker logs sandbox-broker-api 2>&1 | grep "ENG CSP" | tail -5)

if echo "$logs" | grep -q "Using MOCK data"; then
    echo "⚠️  Still in MOCK mode - token may not have been picked up"
    echo "Try: docker compose down && docker compose up -d"
else
    echo "✅ Production mode active (no mock messages found)"
fi

echo ""
echo "Recent ENG CSP logs:"
echo "$logs"

echo ""
echo "=== Test 5: Trigger Manual Sync ==="
echo "Calling POST /v1/admin/sync..."

sync_response=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
    -X POST \
    -H "Authorization: Bearer admin_token_local" \
    "http://localhost:8080/v1/admin/sync")

sync_http_code=$(echo "$sync_response" | grep "HTTP_CODE" | cut -d: -f2)
sync_body=$(echo "$sync_response" | sed '/HTTP_CODE/d')

if [ "$sync_http_code" = "200" ]; then
    echo "✅ Sync successful (HTTP 200)"
    echo "$sync_body" | jq .
else
    echo "❌ Sync failed (HTTP $sync_http_code)"
    echo "$sync_body"
fi

echo ""
echo "=== Test 6: Check Sync Logs ==="
sleep 2
docker logs sandbox-broker-api 2>&1 | grep -A 3 "Fetched.*sandbox accounts" | tail -10

echo ""
echo "=== Test 7: List Sandboxes in Broker ==="
sandboxes=$(curl -s -H "Authorization: Bearer admin_token_local" \
    "http://localhost:8080/v1/admin/sandboxes?limit=5")

count=$(echo "$sandboxes" | jq -r '.sandboxes | length')
echo "Sandboxes in broker: $count"

if [ "$count" -gt 0 ]; then
    echo ""
    echo "Sample sandbox:"
    echo "$sandboxes" | jq -r '.sandboxes[0]'
fi

echo ""
echo "=========================================="
echo "Test Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Check if sandbox count matches: CSP API = $active_sandboxes, Broker = $count"
echo "2. Verify sandbox IDs match between CSP and Broker"
echo "3. Monitor logs: docker logs -f sandbox-broker-api"
echo "4. Check metrics: curl http://localhost:8080/metrics | grep broker_sync"
echo ""
echo "To restore mock mode:"
echo "  git checkout .env"
echo "  docker compose restart api"
