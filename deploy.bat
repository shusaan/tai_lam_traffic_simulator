@echo off
REM AWS Infrastructure deployment script for Tai Lam Traffic Simulator

echo === AWS Infrastructure Deployment ===

REM Check AWS credentials
echo 🔧 Checking AWS credentials...
aws sts get-caller-identity >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ AWS credentials not configured. Run: aws configure
    exit /b 1
)
echo ✅ AWS credentials configured

echo.
echo ⚠️  Required Configuration
echo Before deployment, we need to configure your GitHub username.
echo.

REM Get GitHub username
set /p GITHUB_USERNAME="Enter your GitHub username (example: johndoe): "
if "%GITHUB_USERNAME%"=="" (
    echo ❌ GitHub username is required
    exit /b 1
)

REM Get repository name (with default)
set /p REPO_NAME="Enter repository name (default: tai_lam_traffic_simulator): "
if "%REPO_NAME%"=="" set REPO_NAME=tai_lam_traffic_simulator

echo 🔧 Configuring Terraform variables...
echo github_username = "%GITHUB_USERNAME%" > terraform\terraform.tfvars
echo repository_name = "%REPO_NAME%" >> terraform\terraform.tfvars
echo ✅ Created terraform/terraform.tfvars

echo.
echo ✅ Configuration complete for user: %GITHUB_USERNAME%
echo.

REM Check Terraform
terraform version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Terraform not installed. Install from: https://terraform.io
    exit /b 1
)

REM Bootstrap S3 backend
echo 🔧 Bootstrapping Terraform backend...
set BUCKET_NAME=tai-lam-terraform-state-hk
set REGION=ap-east-1

REM Check if bucket exists
aws s3api head-bucket --bucket %BUCKET_NAME% --region %REGION% >nul 2>&1
if %errorlevel% equ 0 (
    echo ✅ S3 bucket already exists: %BUCKET_NAME%
) else (
    echo Creating S3 bucket: %BUCKET_NAME%
    
    REM Create bucket
    aws s3api create-bucket --bucket %BUCKET_NAME% --region %REGION% --create-bucket-configuration LocationConstraint=%REGION%
    
    REM Enable versioning
    aws s3api put-bucket-versioning --bucket %BUCKET_NAME% --versioning-configuration Status=Enabled
    
    REM Enable encryption
    aws s3api put-bucket-encryption --bucket %BUCKET_NAME% --server-side-encryption-configuration "{\"Rules\":[{\"ApplyServerSideEncryptionByDefault\":{\"SSEAlgorithm\":\"AES256\"}}]}"
    
    REM Block public access
    aws s3api put-public-access-block --bucket %BUCKET_NAME% --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
    
    echo ✅ S3 bucket created: %BUCKET_NAME%
)

REM Deploy infrastructure
echo 🚀 Deploying AWS infrastructure...
cd terraform

REM Initialize Terraform only if needed
if not exist ".terraform" (
    echo Initializing Terraform...
    terraform init
) else if not exist ".terraform.lock.hcl" (
    echo Initializing Terraform...
    terraform init
) else (
    echo ✅ Terraform already initialized
)

REM Apply deployment
terraform apply -auto-approve

REM Get outputs
terraform output -json > ../deployment_outputs.json

echo ✅ Infrastructure deployed successfully!

cd ..

echo.
echo 🎉 AWS Infrastructure Deployed!
echo.
echo Next steps:
echo 1. Add GitHub Secret:
echo    - Go to GitHub Settings ^> Secrets ^> Actions
echo    - Add: AWS_ROLE_ARN = ^(check terraform output github_actions_role_arn^)
echo 2. Push code to GitHub for automatic ECS deployment
echo 3. For local development: docker-compose up --build
echo 4. Check deployment_outputs.json for URLs