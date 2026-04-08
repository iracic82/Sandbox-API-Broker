# Sandbox Pool Dashboard

Streamlit dashboard for visualizing DynamoDB sandbox allocations in **eu-central-1**.

## Features

- 📊 Real-time sandbox pool visualization
- 🗺️ Track name to allocated track mapping
- 📈 Status distribution charts
- 🧹 **NIOSXaaS Cleanup Statistics** - Shows cleaned/skipped/failed/pending counts
- 🔄 Auto-refresh capability
- 📥 CSV export
- 🐳 Docker-ready for EC2 deployment
- 🔐 AWS Cognito authentication via ALB

## NIOSXaaS Cleanup Statistics

The dashboard displays real-time NIOSXaaS cleanup metrics:

| Metric | Description |
|--------|-------------|
| **Cleaned** | Sandboxes where NIOSXaaS services were successfully deleted |
| **Skipped** | Sandboxes with no NIOSXaaS services found |
| **Failed** | Sandboxes where NIOSXaaS cleanup encountered errors |
| **Pending** | Sandboxes awaiting cleanup (status: pending_deletion) |

The statistics are derived from two data sources:
- **SBX# records**: Active sandboxes with cleanup tracking fields
- **NIOSXAAS# records**: Historical cleanup records (preserved after sandbox deletion)

**Note**: NIOSXAAS# cleanup records auto-delete after 30 days via DynamoDB TTL.

## Authentication

The dashboard uses **AWS Cognito** for user authentication via Application Load Balancer (ALB) integration.

**User Pool**: `sandbox-dashboard-users` (eu-central-1_H7vRuXDdQ)

For managing users (add/remove/reset passwords), see [COGNITO_USERS.md](COGNITO_USERS.md).

## Quick Start on EC2

### ✨ Easiest Way: One-Command Deploy

**The image is already built and pushed to ECR!** Just SSH to your EC2 and run:

```bash
# Download and run the deployment script
curl -o deploy.sh https://raw.githubusercontent.com/your-repo/dashboard/deploy-to-ec2.sh
chmod +x deploy.sh
./deploy.sh
```

Or manually:

```bash
# Login to ECR
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 905418046272.dkr.ecr.eu-central-1.amazonaws.com

# Pull and run
docker run -d \
  --name sandbox-dashboard \
  -p 8083:8083 \
  --restart unless-stopped \
  -e AWS_REGION=eu-central-1 \
  -e DDB_TABLE_NAME=sandbox-broker-pool \
  905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest
```

### 🌐 Access Dashboard

Open your browser to:
```
http://YOUR_EC2_PUBLIC_IP:8083
```

---

## Rebuilding and Updating Image

If you need to rebuild and push a new version:

### From Your Local Machine (with okta-sso):

```bash
cd dashboard

# Login to AWS
aws sso login --profile okta-sso

# Build for linux/amd64 (important for EC2!)
docker build --platform linux/amd64 -t sandbox-dashboard:latest .

# Tag and push
docker tag sandbox-dashboard:latest 905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest
aws ecr get-login-password --region eu-central-1 --profile okta-sso | docker login --username AWS --password-stdin 905418046272.dkr.ecr.eu-central-1.amazonaws.com
docker push 905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest
```

### Update on EC2:

```bash
# Use the deployment script
./deploy-to-ec2.sh
```

## EC2 IAM Role Requirements

Your EC2 instance needs an IAM role with DynamoDB read permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Scan",
        "dynamodb:Query",
        "dynamodb:GetItem",
        "dynamodb:DescribeTable"
      ],
      "Resource": [
        "arn:aws:dynamodb:eu-central-1:YOUR_ACCOUNT_ID:table/sandbox-broker-pool",
        "arn:aws:dynamodb:eu-central-1:YOUR_ACCOUNT_ID:table/sandbox-broker-pool/index/*"
      ]
    }
  ]
}
```

## Docker Commands

### View logs:
```bash
docker logs -f sandbox-dashboard
```

### Stop dashboard:
```bash
docker stop sandbox-dashboard
```

### Restart dashboard:
```bash
docker restart sandbox-dashboard
```

### Remove container:
```bash
docker stop sandbox-dashboard
docker rm sandbox-dashboard
```

### Update to new version:
```bash
# Pull latest image
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 905418046272.dkr.ecr.eu-central-1.amazonaws.com
docker pull 905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest

# Stop and remove old container
docker stop sandbox-dashboard
docker rm sandbox-dashboard

# Run new version
docker run -d \
  --name sandbox-dashboard \
  -p 8083:8083 \
  --restart unless-stopped \
  -e AWS_REGION=eu-central-1 \
  -e DDB_TABLE_NAME=sandbox-broker-pool \
  905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_REGION` | `eu-central-1` | AWS region for DynamoDB |
| `DDB_TABLE_NAME` | `sandbox-broker-pool` | DynamoDB table name |

## Security Group Configuration

Make sure your EC2 security group allows inbound traffic on port **8083**:

- **Type:** Custom TCP
- **Port:** 8083
- **Source:** Your IP or internal network (don't expose to 0.0.0.0/0 in production)

## Troubleshooting

### Dashboard not loading?
```bash
# Check if container is running
docker ps

# Check logs for errors
docker logs sandbox-dashboard
```

### DynamoDB access denied?
- Verify EC2 IAM role has correct permissions
- Check AWS region matches (eu-central-1)
- Verify table name is correct

### Port 8083 not accessible?
- Check EC2 security group rules
- Verify container is listening: `docker ps` should show `0.0.0.0:8083->8083/tcp`

## Local Development

To run locally (without Docker):

```bash
cd dashboard
pip install -r requirements.txt

# Set environment variables
export AWS_REGION=eu-central-1
export DDB_TABLE_NAME=sandbox-broker-pool

# Run streamlit
streamlit run app.py --server.port=8083
```

## Architecture

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ :8083
       ▼
┌─────────────────────┐
│  EC2 Instance       │
│  ┌───────────────┐  │
│  │   Docker      │  │
│  │  Container    │  │
│  │  (Streamlit)  │  │
│  └───────┬───────┘  │
│          │          │
│   (IAM Role Auth)   │
└──────────┼──────────┘
           │
           ▼
    ┌──────────────┐
    │  DynamoDB    │
    │ (Read-Only)  │
    │ eu-central-1 │
    └──────────────┘
```

## Notes

- Dashboard is **read-only** - it never modifies production data
- Auto-refresh can be enabled in the sidebar
- Data is cached for 30 seconds for performance
- CSV export available for all filtered data
- No AWS credentials needed on EC2 (uses IAM role)
