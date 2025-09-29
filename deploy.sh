#!/bin/bash

# AWS Infrastructure deployment script for Tai Lam Traffic Simulator

set -e

echo "=== AWS Infrastructure Deployment ==="

# Check AWS credentials
echo "🔧 Checking AWS credentials..."
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS credentials not configured. Run: aws configure"
    exit 1
fi
echo "✅ AWS credentials configured"

# Check Terraform
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform not installed. Install from: https://terraform.io"
    exit 1
fi

# Bootstrap S3 backend
echo "🔧 Bootstrapping Terraform backend..."
BUCKET_NAME="tai-lam-terraform-state-hk"
REGION="ap-east-1"

# Check if bucket exists
if aws s3api head-bucket --bucket "$BUCKET_NAME" --region "$REGION" 2>/dev/null; then
    echo "✅ S3 bucket already exists: $BUCKET_NAME"
else
    echo "Creating S3 bucket: $BUCKET_NAME"
    
    # Create bucket
    if [ "$REGION" = "us-east-1" ]; then
        aws s3api create-bucket --bucket "$BUCKET_NAME" --region "$REGION"
    else
        aws s3api create-bucket --bucket "$BUCKET_NAME" --region "$REGION" \
            --create-bucket-configuration LocationConstraint="$REGION"
    fi
    
    # Enable versioning
    aws s3api put-bucket-versioning --bucket "$BUCKET_NAME" \
        --versioning-configuration Status=Enabled
    
    # Enable encryption
    aws s3api put-bucket-encryption --bucket "$BUCKET_NAME" \
        --server-side-encryption-configuration '{
            "Rules": [{
                "ApplyServerSideEncryptionByDefault": {
                    "SSEAlgorithm": "AES256"
                }
            }]
        }'
    
    # Block public access
    aws s3api put-public-access-block --bucket "$BUCKET_NAME" \
        --public-access-block-configuration \
        BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
    
    echo "✅ S3 bucket created: $BUCKET_NAME"
fi

# Deploy infrastructure
echo "🚀 Deploying AWS infrastructure..."
cd terraform

# Initialize Terraform only if needed
if [ ! -d ".terraform" ] || [ ! -f ".terraform.lock.hcl" ]; then
    echo "Initializing Terraform..."
    terraform init
else
    echo "✅ Terraform already initialized"
fi

# Apply deployment
terraform apply -auto-approve

# Get outputs
terraform output -json > ../deployment_outputs.json

echo "✅ Infrastructure deployed successfully!"

cd ..

echo ""
echo "🎉 AWS Infrastructure Deployed!"
echo ""
echo "Next steps:"
echo "1. Push code to GitHub for automatic ECS deployment"
echo "2. For local development: docker-compose up --build"

# Show outputs
if [ -f deployment_outputs.json ]; then
    if command -v jq &> /dev/null; then
        echo "3. Production URL: http://$(jq -r '.load_balancer_dns.value' deployment_outputs.json 2>/dev/null || echo 'N/A')"
        echo "4. API URL: $(jq -r '.api_gateway_url.value' deployment_outputs.json 2>/dev/null || echo 'N/A')"
    else
        echo "3. Check deployment_outputs.json for URLs"
    fi
fi