#!/bin/bash
# Phase 4 Security Features Test Script

BASE_URL="http://localhost:8080"
ADMIN_TOKEN="admin_token_local"

echo "=========================================="
echo "Phase 4: Security Features Test"
echo "=========================================="

echo -e "\n1. Security Headers Test"
echo "---"
headers=$(curl -s -I "$BASE_URL/healthz" | grep -iE "x-frame|x-content|strict-transport|content-security|referrer-policy")
echo "$headers"
if echo "$headers" | grep -q "x-frame-options"; then
    echo "✅ Security headers present"
else
    echo "❌ Security headers missing"
fi

echo -e "\n2. Rate Limiting Test (burst capacity 20)"
echo "---"
echo "Sending 25 rapid requests..."
success_count=0
rate_limited_count=0
for i in {1..25}; do
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/v1/admin/stats" -H "Authorization: Bearer $ADMIN_TOKEN")
    if [ "$http_code" = "200" ]; then
        ((success_count++))
    elif [ "$http_code" = "429" ]; then
        ((rate_limited_count++))
    fi
done
echo "Success: $success_count, Rate Limited: $rate_limited_count"
if [ $rate_limited_count -gt 0 ]; then
    echo "✅ Rate limiting working"
else
    echo "⚠️  No rate limiting detected (may need to send faster)"
fi

echo -e "\n3. Rate Limit Headers"
echo "---"
rate_headers=$(curl -s -I "$BASE_URL/v1/admin/stats" -H "Authorization: Bearer $ADMIN_TOKEN" | grep -i ratelimit)
echo "$rate_headers"
if echo "$rate_headers" | grep -q "x-ratelimit-limit"; then
    echo "✅ Rate limit headers present"
else
    echo "❌ Rate limit headers missing"
fi

echo -e "\n4. CORS Headers Test"
echo "---"
cors_headers=$(curl -s -I -X OPTIONS "$BASE_URL/v1/admin/stats" \
    -H "Origin: https://example.com" \
    -H "Access-Control-Request-Method: GET" | grep -i "access-control")
echo "$cors_headers"
if echo "$cors_headers" | grep -q "access-control-allow"; then
    echo "✅ CORS headers present"
else
    echo "❌ CORS headers missing"
fi

echo -e "\n5. Health Check Bypass (no rate limiting)"
echo "---"
echo "Sending 30 health check requests..."
health_fail=0
for i in {1..30}; do
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/healthz")
    if [ "$http_code" != "200" ]; then
        ((health_fail++))
    fi
done
if [ $health_fail -eq 0 ]; then
    echo "✅ All 30 health checks passed (bypassed rate limiting)"
else
    echo "❌ $health_fail health checks failed"
fi

echo -e "\n6. Metrics Endpoint Check"
echo "---"
metrics=$(curl -s "$BASE_URL/metrics" | grep "broker_pool_total")
if [ -n "$metrics" ]; then
    echo "✅ Metrics endpoint accessible"
    echo "   $metrics"
else
    echo "❌ Metrics endpoint not accessible"
fi

echo -e "\n=========================================="
echo "Phase 4 Security Test Complete"
echo "=========================================="
