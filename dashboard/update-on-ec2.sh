#!/bin/bash

# Script to update the dashboard on EC2
# Run this script on the EC2 instance

set -e

echo "=== Updating Sandbox Dashboard on EC2 ==="
echo ""

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 905418046272.dkr.ecr.eu-central-1.amazonaws.com

# Pull latest image
echo "📦 Pulling latest dashboard image..."
docker pull 905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest

# Stop and remove old container
echo "🛑 Stopping old container..."
docker stop sandbox-dashboard || true
docker rm sandbox-dashboard || true

# Start new container
echo "🚀 Starting new container..."
docker run -d \
  --name sandbox-dashboard \
  -p 8083:8083 \
  --restart unless-stopped \
  -e AWS_REGION=eu-central-1 \
  -e DDB_TABLE_NAME=sandbox-broker-pool \
  905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest

# Wait a bit for container to start
echo "⏳ Waiting for container to start..."
sleep 5

# Check status
echo ""
echo "✅ Container status:"
docker ps | grep sandbox-dashboard

echo ""
echo "📋 Recent logs:"
docker logs --tail 20 sandbox-dashboard

echo ""
echo "=== Update Complete! ==="
echo "Dashboard is now running at: http://18.195.146.51:8083"
echo ""
echo "To view live logs: docker logs -f sandbox-dashboard"
