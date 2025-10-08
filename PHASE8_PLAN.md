# Phase 8: CI/CD Pipeline - Implementation Plan

**Status**: 📋 **PLANNING** - Ready to implement when needed
**Date**: 2025-10-08
**Risk Level**: 🛡️ **ZERO** - Can be implemented without touching production

---

## Overview

Automate the deployment pipeline from code push to production while maintaining **zero production impact** during implementation. All workflows will be created in "safe mode" with manual triggers only.

**Current State**:
- ✅ Production is live and stable
- ✅ Manual deployments work perfectly (Docker build → ECR push → ECS update)
- ❌ No GitHub Actions workflows exist
- ❌ No automated testing on PRs
- ❌ No automated deployments

**Goal**: Build CI/CD infrastructure that provides immediate value (automated testing) without risking production stability.

---

## Safe Implementation Strategy

### Core Principle: Build First, Enable Later

All workflows will be created with **manual triggers only** or **read-only operations**. Nothing will automatically deploy to production until explicitly enabled.

**Safety Levels**:
- **Level 0 (Current)**: No automation, all manual
- **Level 1 (Phase 8.1)**: Automated testing only (zero AWS access)
- **Level 2 (Phase 8.2)**: Docker build validation (no ECR push)
- **Level 3 (Phase 8.3)**: Terraform validation (read-only)
- **Level 4 (Phase 8.4)**: Manual-trigger deployment workflow (disabled by default)
- **Level 5 (Future)**: Full automation (only when ready, weeks/months later)

**We'll implement Levels 1-4 in Phase 8, keeping Level 5 optional for future.**

---

## Phase 8 Deliverables

### 8.1: Automated Testing Workflow ✅ ZERO RISK

**File**: `.github/workflows/test.yml`

**Trigger**: On every Pull Request to `main`

**What it does**:
- Runs `pytest tests/unit/` (33 tests)
- Runs `pytest tests/integration/` (18 tests)
- Generates code coverage report
- Posts results as PR comment
- Blocks merge if tests fail

**AWS Access**: NONE

**Production Impact**: ZERO - Tests run in GitHub's isolated Ubuntu runners

**Value**:
- Catch bugs before merge
- Enforce code quality
- No manual pytest needed
- Free for public repos

**Implementation Time**: 30 minutes

**Dependencies**:
```yaml
Python 3.11
pytest
pytest-asyncio
pytest-cov
httpx (for integration tests)
```

**Example Workflow**:
```yaml
name: Test Suite

on:
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-asyncio pytest-cov httpx

      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=app --cov-report=xml

      - name: Run integration tests
        run: pytest tests/integration/ -v

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: unittests
```

**Success Criteria**:
- ✅ All 33 unit tests pass
- ✅ All 18 integration tests pass
- ✅ Coverage report generated
- ✅ PR blocked if tests fail

---

### 8.2: Docker Build Validation ✅ ZERO RISK

**File**: `.github/workflows/build.yml`

**Trigger**: On Pull Request when Dockerfile changes

**What it does**:
- Validates Dockerfile syntax
- Builds Docker image
- Tests multi-stage build works
- **Does NOT push to ECR**

**AWS Access**: NONE

**Production Impact**: ZERO - Only tests local build

**Value**:
- Catch Dockerfile errors early
- Validate dependencies resolve
- Test build time

**Implementation Time**: 20 minutes

**Example Workflow**:
```yaml
name: Docker Build Validation

on:
  pull_request:
    paths:
      - 'Dockerfile'
      - 'requirements.txt'

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Build Docker image (no push)
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: sandbox-broker-api:test
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Test image
        run: |
          docker run --rm sandbox-broker-api:test --version || echo "Built successfully"
```

**Success Criteria**:
- ✅ Dockerfile builds without errors
- ✅ All dependencies install correctly
- ✅ Image size reasonable (<500MB)

---

### 8.3: Terraform Validation ✅ ZERO RISK

**File**: `.github/workflows/terraform.yml`

**Trigger**: On Pull Request when `terraform/**` changes

**What it does**:
- Runs `terraform fmt -check` (formatting)
- Runs `terraform validate` (syntax)
- Runs `terraform plan` (preview changes)
- Runs `tfsec` (security scan)
- Posts plan as PR comment
- **Does NOT run `terraform apply`**

**AWS Access**: READ-ONLY (for terraform plan)

**Production Impact**: ZERO - Read-only operations

**Value**:
- Catch Terraform errors before merge
- Preview infrastructure changes
- Security scanning
- Enforce formatting standards

**Implementation Time**: 45 minutes

**Dependencies**:
- Terraform CLI
- tfsec (security scanner)
- AWS credentials (read-only)

**Example Workflow**:
```yaml
name: Terraform Validation

on:
  pull_request:
    paths:
      - 'terraform/**'

jobs:
  terraform:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Terraform
        uses: hashicorp/setup-terraform@v3
        with:
          terraform_version: 1.5.0

      - name: Terraform Format Check
        run: terraform fmt -check -recursive terraform/

      - name: Terraform Init
        run: |
          cd terraform
          terraform init -backend=false

      - name: Terraform Validate
        run: |
          cd terraform
          terraform validate

      - name: Terraform Plan (read-only)
        run: |
          cd terraform
          terraform plan -no-color
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: eu-central-1

      - name: Security Scan with tfsec
        uses: aquasecurity/tfsec-action@v1.0.0
        with:
          working_directory: terraform
```

**Success Criteria**:
- ✅ Terraform syntax valid
- ✅ Formatting correct
- ✅ No security issues found
- ✅ Plan shows expected changes

---

### 8.4: Manual Deployment Workflow ⚠️ REQUIRES MANUAL TRIGGER

**File**: `.github/workflows/deploy.yml`

**Trigger**: **MANUAL ONLY** (`workflow_dispatch`)

**What it does**:
- Builds Docker image
- Pushes to ECR
- Updates ECS task definition
- Deploys to ECS cluster
- Waits for health checks
- Rolls back if deployment fails

**AWS Access**: WRITE (ECR, ECS)

**Production Impact**: **CONTROLLED** - Only runs when you manually trigger it

**Value**:
- Automates deployment process
- Standardizes deployments
- Reduces human error
- Rollback capability

**Implementation Time**: 1-2 hours

**Security Requirements**:
- AWS OIDC identity provider (no long-lived credentials)
- IAM role with limited permissions (ECR push, ECS deploy only)
- GitHub environment protection rules

**Example Workflow**:
```yaml
name: Deploy to Production

on:
  workflow_dispatch:
    inputs:
      confirm:
        description: 'Type "DEPLOY" to confirm deployment to production'
        required: true
      version:
        description: 'Version tag (optional, defaults to git SHA)'
        required: false

jobs:
  deploy:
    runs-on: ubuntu-latest

    # Safety check: require exact confirmation text
    if: github.event.inputs.confirm == 'DEPLOY'

    # Use GitHub environment for additional protection
    environment:
      name: production
      url: https://api-sandbox-broker.highvelocitynetworking.com

    steps:
      - uses: actions/checkout@v4

      - name: Configure AWS credentials (OIDC)
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::905418046272:role/GithubActionsDeployRole
          aws-region: eu-central-1

      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build Docker image
        run: |
          IMAGE_TAG=${{ github.event.inputs.version || github.sha }}
          docker build --platform linux/amd64 \
            -t ${{ steps.login-ecr.outputs.registry }}/sandbox-broker-api:$IMAGE_TAG \
            -t ${{ steps.login-ecr.outputs.registry }}/sandbox-broker-api:latest \
            .

      - name: Push to ECR
        run: |
          IMAGE_TAG=${{ github.event.inputs.version || github.sha }}
          docker push ${{ steps.login-ecr.outputs.registry }}/sandbox-broker-api:$IMAGE_TAG
          docker push ${{ steps.login-ecr.outputs.registry }}/sandbox-broker-api:latest

      - name: Update ECS task definition
        id: task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: sandbox-broker-api
          image: ${{ steps.login-ecr.outputs.registry }}/sandbox-broker-api:${{ github.event.inputs.version || github.sha }}

      - name: Deploy to ECS
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: ${{ steps.task-def.outputs.task-definition }}
          service: sandbox-broker-api
          cluster: sandbox-broker-cluster
          wait-for-service-stability: true

      - name: Verify deployment
        run: |
          echo "Checking health endpoint..."
          sleep 30
          curl -f https://api-sandbox-broker.highvelocitynetworking.com/v1/healthz || exit 1
```

**Success Criteria**:
- ✅ Requires manual trigger (no auto-deploy)
- ✅ Requires confirmation text
- ✅ Uses OIDC (no long-lived credentials)
- ✅ Waits for health checks
- ✅ Rolls back on failure

---

### 8.5: Rollback Workflow ⚠️ MANUAL TRIGGER

**File**: `.github/workflows/rollback.yml`

**Trigger**: **MANUAL ONLY** (`workflow_dispatch`)

**What it does**:
- Lists recent ECS task definitions
- Rolls back to specified revision
- Verifies health checks

**AWS Access**: WRITE (ECS)

**Production Impact**: **CONTROLLED** - Emergency rollback only

**Example Workflow**:
```yaml
name: Rollback to Previous Version

on:
  workflow_dispatch:
    inputs:
      task_revision:
        description: 'Task definition revision number to rollback to'
        required: true
      confirm:
        description: 'Type "ROLLBACK" to confirm'
        required: true

jobs:
  rollback:
    runs-on: ubuntu-latest
    if: github.event.inputs.confirm == 'ROLLBACK'

    steps:
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::905418046272:role/GithubActionsDeployRole
          aws-region: eu-central-1

      - name: Rollback ECS service
        run: |
          aws ecs update-service \
            --cluster sandbox-broker-cluster \
            --service sandbox-broker-api \
            --task-definition sandbox-broker-api:${{ github.event.inputs.task_revision }} \
            --force-new-deployment

      - name: Wait for stability
        run: |
          aws ecs wait services-stable \
            --cluster sandbox-broker-cluster \
            --services sandbox-broker-api

      - name: Verify health
        run: |
          curl -f https://api-sandbox-broker.highvelocitynetworking.com/v1/healthz
```

---

## AWS OIDC Setup (Required for 8.4 and 8.5)

**Purpose**: Allow GitHub Actions to authenticate with AWS without storing long-lived credentials.

**Setup Steps** (only needed when enabling deployment workflows):

### 1. Create GitHub OIDC Identity Provider in AWS

```bash
# Create OIDC provider
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 \
  --profile okta-sso --region eu-central-1
```

### 2. Create IAM Role for GitHub Actions

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::905418046272:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com",
          "token.actions.githubusercontent.com:sub": "repo:YOUR_GITHUB_ORG/Sandbox-API-Broker:ref:refs/heads/main"
        }
      }
    }
  ]
}
```

### 3. Attach Policies to Role

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetAuthorizationToken",
        "ecr:BatchCheckLayerAvailability",
        "ecr:GetDownloadUrlForLayer",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "ecs:UpdateService",
        "ecs:DescribeServices",
        "ecs:RegisterTaskDefinition",
        "ecs:DescribeTaskDefinition"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:PassRole"
      ],
      "Resource": "arn:aws:iam::905418046272:role/ecsTaskExecutionRole"
    }
  ]
}
```

**Note**: This setup is only needed when you're ready to enable deployment workflows (8.4+). Not needed for testing workflows (8.1-8.3).

---

## GitHub Secrets Configuration

**Required for all workflows**:
- (None - testing workflows need no secrets)

**Required for deployment workflows (8.4+)**:
```bash
# In GitHub repo: Settings → Secrets and variables → Actions

AWS_REGION=eu-central-1
AWS_ACCOUNT_ID=905418046272
ECR_REPOSITORY=sandbox-broker-api
ECS_CLUSTER=sandbox-broker-cluster
ECS_SERVICE=sandbox-broker-api
```

**Note**: No `AWS_ACCESS_KEY_ID` or `AWS_SECRET_ACCESS_KEY` needed - we use OIDC instead.

---

## Implementation Timeline

### Phase 8.1: Testing Workflows (Week 1)
**Effort**: 1-2 hours
**Risk**: Zero

- [ ] Create `.github/workflows/test.yml`
- [ ] Test on a dummy PR
- [ ] Verify all tests pass
- [ ] Merge to main
- [ ] Monitor for 1 week

**Result**: Automated testing on every PR, zero production changes

---

### Phase 8.2: Build Validation (Week 2)
**Effort**: 30 minutes
**Risk**: Zero

- [ ] Create `.github/workflows/build.yml`
- [ ] Test Docker build in CI
- [ ] Verify build succeeds
- [ ] Merge to main

**Result**: Dockerfile validation, zero production changes

---

### Phase 8.3: Terraform Validation (Week 3)
**Effort**: 1 hour
**Risk**: Zero (read-only)

- [ ] Create `.github/workflows/terraform.yml`
- [ ] Set up AWS read-only credentials
- [ ] Test terraform plan
- [ ] Merge to main

**Result**: Infrastructure validation, zero production changes

---

### Phase 8.4: Manual Deployment (Week 4+)
**Effort**: 2-3 hours
**Risk**: Controlled (manual trigger only)

- [ ] Set up AWS OIDC provider
- [ ] Create IAM role for GitHub Actions
- [ ] Create `.github/workflows/deploy.yml`
- [ ] Test deployment workflow ONCE manually
- [ ] Leave it disabled for regular use

**Result**: Deployment automation ready, but not used by default

---

### Phase 8.5: Rollback Workflow (Week 5+)
**Effort**: 30 minutes
**Risk**: Controlled (emergency use only)

- [ ] Create `.github/workflows/rollback.yml`
- [ ] Document how to use it
- [ ] Test in non-production first

**Result**: Emergency rollback capability

---

## Decision Points

### When to Enable Auto-Deploy?

**Current Plan**: NEVER (keep manual deployments)

**If you change your mind later**, you can enable by:
1. Change `workflow_dispatch` to `push: branches: [main]`
2. Remove confirmation input requirement
3. Remove environment protection

**Recommendation**: Keep manual deployments for at least 3-6 months. Let testing workflows prove their value first.

---

## Success Metrics

### After Phase 8.1 (Testing)
- ✅ 100% of PRs have tests run automatically
- ✅ Zero broken code merged to main
- ✅ Test coverage visible in PR comments

### After Phase 8.2 (Build)
- ✅ Dockerfile errors caught before merge
- ✅ Build time tracked in CI

### After Phase 8.3 (Terraform)
- ✅ Infrastructure changes reviewed before merge
- ✅ Security issues caught by tfsec

### After Phase 8.4 (Deployment - Optional)
- ✅ Deployment workflow exists but unused
- ✅ Ready to use in emergency
- ✅ Tested at least once successfully

---

## Rollback Strategy

If any workflow causes issues:

**Step 1: Disable the workflow**
```bash
# Add this to the workflow file
on: []  # Disables all triggers
```

**Step 2: Delete the workflow file**
```bash
git rm .github/workflows/problematic-workflow.yml
git commit -m "Disable problematic workflow"
git push
```

**Step 3: Revert the commit**
```bash
git revert <commit-sha>
git push
```

**No AWS resources are modified** - Workflows are just files in the repo.

---

## Cost Analysis

**Phase 8.1-8.3 (Testing)**:
- **Cost**: $0 (free for public repos, 2000 minutes/month for private repos)
- **AWS Costs**: $0 (no AWS access)

**Phase 8.4-8.5 (Deployment)**:
- **GitHub Actions**: $0 (deployment runs ~5 min/month)
- **AWS Costs**: $0 (no additional AWS resources)

**Total Additional Cost**: **$0/month**

---

## Next Steps

1. **Review this plan** - Make sure you're comfortable with the approach
2. **Start with 8.1** - Automated testing only (safest)
3. **Run for 2 weeks** - Build confidence
4. **Add 8.2** - Build validation
5. **Add 8.3** - Terraform validation
6. **Stop there** - Keep manual deployments indefinitely
7. **8.4-8.5 optional** - Only if you want deployment automation later

---

## Questions to Decide Before Starting

1. **Do you want automated testing on PRs?** (Recommendation: Yes, zero risk)
2. **Do you want Docker build validation?** (Recommendation: Yes, zero risk)
3. **Do you want Terraform validation?** (Recommendation: Yes, minimal risk)
4. **Do you want deployment automation?** (Recommendation: No, keep manual)
5. **Do you want rollback workflow?** (Recommendation: Maybe, for emergencies)

---

## References

- **Current Deployment Process**: Manual Docker build → ECR push → ECS update
- **Production URL**: https://api-sandbox-broker.highvelocitynetworking.com/v1
- **ECS Cluster**: sandbox-broker-cluster
- **ECR Repository**: 905418046272.dkr.ecr.eu-central-1.amazonaws.com/sandbox-broker-api
- **Current Task Revision**: 6
- **Region**: eu-central-1

---

**Status**: 📋 Ready to implement when needed
**Recommendation**: Start with 8.1 (testing only) for immediate value with zero risk
**Owner**: Igor Racic
**Last Updated**: 2025-10-08
