#!/bin/bash
# Deployment script for Sandbox Dashboard on EC2
# Run this script on your EC2 instance

set -e

echo "🚀 Deploying Sandbox Dashboard to EC2..."

# Variables
ECR_REGISTRY="905418046272.dkr.ecr.eu-central-1.amazonaws.com"
IMAGE_NAME="sandbox-dashboard"
CONTAINER_NAME="sandbox-dashboard"
PORT=8083

# Login to ECR
echo "📦 Logging in to ECR..."
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin $ECR_REGISTRY

# Pull latest image
echo "⬇️  Pulling latest image..."
docker pull $ECR_REGISTRY/$IMAGE_NAME:latest

# Stop and remove existing container if running
echo "🛑 Stopping existing container (if any)..."
docker stop $CONTAINER_NAME 2>/dev/null || true
docker rm $CONTAINER_NAME 2>/dev/null || true

# Run new container
echo "▶️  Starting new container..."
docker run -d \
  --name $CONTAINER_NAME \
  -p $PORT:$PORT \
  --restart unless-stopped \
  -e AWS_REGION=eu-central-1 \
  -e DDB_TABLE_NAME=sandbox-broker-pool \
  $ECR_REGISTRY/$IMAGE_NAME:latest

# Wait for container to be healthy
echo "⏳ Waiting for container to be healthy..."
sleep 5

# Check container status
if docker ps | grep -q $CONTAINER_NAME; then
  echo "✅ Dashboard deployed successfully!"
  echo ""
  echo "🌐 Access the dashboard at: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):$PORT"
  echo ""
  echo "📋 Useful commands:"
  echo "  - View logs: docker logs -f $CONTAINER_NAME"
  echo "  - Stop: docker stop $CONTAINER_NAME"
  echo "  - Restart: docker restart $CONTAINER_NAME"
else
  echo "❌ Deployment failed! Check logs with: docker logs $CONTAINER_NAME"
  exit 1
fi
