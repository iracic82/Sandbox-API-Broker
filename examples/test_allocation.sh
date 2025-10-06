#!/bin/bash
# Test allocation script - runs the allocation and shows results

set -e

echo "🧪 Testing Sandbox Broker Allocation"
echo "===================================="
echo ""

# Check for required env vars
if [ -z "$BROKER_API_TOKEN" ]; then
    echo "❌ BROKER_API_TOKEN not set"
    echo ""
    echo "Get it from AWS Secrets Manager:"
    echo "  aws secretsmanager get-secret-value \\"
    echo "    --secret-id sandbox-broker-broker-api-token \\"
    echo "    --region eu-central-1 --profile okta-sso \\"
    echo "    --query SecretString --output text"
    exit 1
fi

# Set test values (simulate Instruqt environment)
export INSTRUQT_PARTICIPANT_ID="test-student-$(date +%s)-$$"
export INSTRUQT_TRACK_SLUG="test-lab-run"
export BROKER_API_URL="https://api-sandbox-broker.highvelocitynetworking.com/v1"

echo "📋 Configuration:"
echo "   API URL: $BROKER_API_URL"
echo "   Student ID: $INSTRUQT_PARTICIPANT_ID"
echo "   Lab: $INSTRUQT_TRACK_SLUG"
echo ""

# Run allocation
echo "🚀 Running allocation..."
python3 instruqt_broker_allocation.py

echo ""
echo "📂 Generated Files:"
echo "==================="

if [ -f sandbox_id.txt ]; then
    echo ""
    echo "sandbox_id.txt:"
    cat sandbox_id.txt
    echo ""
fi

if [ -f external_id.txt ]; then
    echo ""
    echo "external_id.txt:"
    cat external_id.txt
    echo ""
fi

if [ -f sandbox_name.txt ]; then
    echo ""
    echo "sandbox_name.txt:"
    cat sandbox_name.txt
    echo ""
fi

if [ -f sandbox_env.sh ]; then
    echo ""
    echo "sandbox_env.sh:"
    cat sandbox_env.sh
    echo ""
fi

echo ""
echo "✅ Test Complete!"
echo ""
echo "To clean up the allocation, run:"
echo "  python3 instruqt_broker_cleanup.py"
