# EC2 Deployment Commands

## 🎯 Quick Copy-Paste Commands for Your EC2 Instance

### Step 1: SSH to Your EC2 Instance

```bash
ssh ec2-user@YOUR_EC2_IP
```

### Step 2: Install Docker (if not already installed)

```bash
# For Amazon Linux 2023
sudo yum update -y
sudo yum install docker -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -a -G docker ec2-user

# Log out and back in for group changes to take effect
exit
# SSH back in
```

### Step 3: Deploy the Dashboard

```bash
# Login to ECR
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 905418046272.dkr.ecr.eu-central-1.amazonaws.com

# Pull and run the dashboard
docker run -d \
  --name sandbox-dashboard \
  -p 8083:8083 \
  --restart unless-stopped \
  -e AWS_REGION=eu-central-1 \
  -e DDB_TABLE_NAME=sandbox-broker-pool \
  905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest
```

### Step 4: Verify It's Running

```bash
# Check container status
docker ps | grep sandbox-dashboard

# View logs
docker logs -f sandbox-dashboard
```

### Step 5: Access the Dashboard

Open your browser to:
```
http://YOUR_EC2_PUBLIC_IP:8083
```

---

## 🔧 Management Commands

### View Logs
```bash
docker logs -f sandbox-dashboard
```

### Stop Dashboard
```bash
docker stop sandbox-dashboard
```

### Start Dashboard
```bash
docker start sandbox-dashboard
```

### Restart Dashboard
```bash
docker restart sandbox-dashboard
```

### Update to Latest Version
```bash
# Login to ECR
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 905418046272.dkr.ecr.eu-central-1.amazonaws.com

# Pull latest
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

---

## ⚠️ Prerequisites

### 1. EC2 IAM Role

Your EC2 instance must have an IAM role with DynamoDB read permissions:

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
        "arn:aws:dynamodb:eu-central-1:905418046272:table/sandbox-broker-pool",
        "arn:aws:dynamodb:eu-central-1:905418046272:table/sandbox-broker-pool/index/*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage"
      ],
      "Resource": "*"
    }
  ]
}
```

### 2. Security Group

Allow inbound traffic on port 8083:
- **Type:** Custom TCP
- **Port:** 8083
- **Source:** Your IP (e.g., `YOUR_IP/32`) or internal network

---

## 📊 ECR Image Details

- **Registry:** `905418046272.dkr.ecr.eu-central-1.amazonaws.com`
- **Repository:** `sandbox-dashboard`
- **Image:** `905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest`
- **Region:** `eu-central-1`
- **Port:** `8083`

---

## 🐛 Troubleshooting

### Can't pull image from ECR?
```bash
# Check IAM role has ECR permissions
aws ecr describe-repositories --region eu-central-1

# Re-login to ECR
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin 905418046272.dkr.ecr.eu-central-1.amazonaws.com
```

### Dashboard shows DynamoDB errors?
```bash
# Check IAM role has DynamoDB permissions
aws dynamodb describe-table --table-name sandbox-broker-pool --region eu-central-1

# Check logs
docker logs sandbox-dashboard
```

### Can't access dashboard from browser?
- Check security group allows port 8083
- Verify container is running: `docker ps`
- Check EC2 public IP: `curl http://169.254.169.254/latest/meta-data/public-ipv4`

---

## ✅ Image Already Built and Pushed

The Docker image is **already built** and available in ECR at:
```
905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-dashboard:latest
```

Built for: **linux/amd64** (compatible with AWS Linux EC2 instances)

You just need to pull and run it on your EC2 instance!
