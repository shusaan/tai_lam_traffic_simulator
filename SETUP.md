# 🚀 Setup Checklist

## Required User Configuration

### 1. GitHub Username Configuration
**File**: `terraform/github_oidc.tf` (line 32)

**Find this line:**
```hcl
"token.actions.githubusercontent.com:sub" = "repo:YOUR_GITHUB_USERNAME/tai_lam_traffic_simulator:*"
```

**Replace with your GitHub username:**
```hcl
"token.actions.githubusercontent.com:sub" = "repo:johndoe/tai_lam_traffic_simulator:*"
```

### 2. Docker Image URL Configuration
**File**: `terraform/ecs_deployment.tf`

**Find this line:**
```hcl
image = "ghcr.io/YOUR_GITHUB_USERNAME/tai_lam_traffic_simulator:latest"
```

**Replace with your GitHub username:**
```hcl
image = "ghcr.io/johndoe/tai_lam_traffic_simulator:latest"
```

## Deployment Steps

### 1. Deploy Infrastructure
```bash
# Linux/macOS
./deploy.sh

# Windows
deploy.bat
```

### 2. Get GitHub Actions Role ARN
```bash
cd terraform
terraform output github_actions_role_arn
```

### 3. Configure GitHub Repository
1. Go to your GitHub repository
2. **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add:
   - **Name**: `AWS_ROLE_ARN`
   - **Value**: [output from step 2]

### 4. Enable GitHub Actions
1. **Settings** → **Actions** → **General**
2. **Actions permissions**: Allow all actions and reusable workflows
3. **Workflow permissions**: Read and write permissions

### 5. Deploy Application
```bash
git add .
git commit -m "Configure OIDC and deploy"
git push origin main
```

## Verification

### Check Infrastructure
```bash
# Check ECS cluster
aws ecs describe-clusters --clusters tai-lam-poc-cluster

# Check load balancer
aws elbv2 describe-load-balancers --names tai-lam-poc-alb
```

### Check GitHub Actions
1. Go to **Actions** tab in your GitHub repository
2. Verify the workflow runs successfully
3. Check deployment logs

### Test Endpoints
- **Production**: Check `deployment_outputs.json` for load balancer DNS
- **API**: Check `deployment_outputs.json` for API Gateway URL

## Common Issues

### OIDC Authentication Fails
- ✅ Verify GitHub username in `github_oidc.tf`
- ✅ Check repository name matches exactly
- ✅ Ensure `AWS_ROLE_ARN` secret is correct

### ECS Deployment Fails
- ✅ Check GitHub Container Registry permissions
- ✅ Verify image URL in `ecs_deployment.tf`
- ✅ Check ECS service logs in CloudWatch

### Terraform Errors
- ✅ Run `terraform init` if providers changed
- ✅ Check AWS credentials: `aws sts get-caller-identity`
- ✅ Verify region is `ap-east-1` (Hong Kong)