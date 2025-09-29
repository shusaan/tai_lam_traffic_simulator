# S3 bucket for ML model storage
resource "aws_s3_bucket" "model_storage" {
  bucket = "${var.project_name}-models"
  
  tags = {
    Name = "${var.project_name}-models"
    Purpose = "ML model storage"
  }
}

resource "aws_s3_bucket_versioning" "model_versioning" {
  bucket = aws_s3_bucket.model_storage.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "model_encryption" {
  bucket = aws_s3_bucket.model_storage.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# IAM policy for model access
resource "aws_iam_policy" "model_access" {
  name = "${var.project_name}-model-access"
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.model_storage.arn,
          "${aws_s3_bucket.model_storage.arn}/*"
        ]
      }
    ]
  })
}

# Attach policy to Lambda role
resource "aws_iam_role_policy_attachment" "lambda_model_access" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.model_access.arn
}

# Output bucket name
output "model_s3_bucket" {
  description = "S3 bucket for ML models"
  value       = aws_s3_bucket.model_storage.bucket
}