terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-east-1"  # Hong Kong region
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "tai-lam-poc"
}

variable "github_username" {
  description = "GitHub username for OIDC and container registry"
  type        = string
  default     = "example-user"
}

variable "repository_name" {
  description = "GitHub repository name"
  type        = string
  default     = "tai_lam_traffic_simulator"
}

# DynamoDB Tables (Free Tier: 25GB storage, 25 RCU/WCU)
resource "aws_dynamodb_table" "traffic_data" {
  name           = "${var.project_name}-traffic"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5   # Free tier limit
  write_capacity = 5   # Free tier limit
  hash_key       = "timestamp"

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Name = "${var.project_name}-traffic"
    Tier = "free"
  }
}

resource "aws_dynamodb_table" "toll_history" {
  name           = "${var.project_name}-tolls"
  billing_mode   = "PROVISIONED"
  read_capacity  = 5
  write_capacity = 5
  hash_key       = "timestamp"

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Name = "${var.project_name}-tolls"
    Tier = "free"
  }
}

# IAM Role for Lambda (Free Tier: 1M requests/month)
resource "aws_iam_role" "lambda_role" {
  name = "${var.project_name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan"
        ]
        Resource = [
          aws_dynamodb_table.traffic_data.arn,
          aws_dynamodb_table.toll_history.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = "${aws_s3_bucket.model_storage.arn}/*"
      }
    ]
  })
}

# Lambda function with AI model support
resource "aws_lambda_function" "toll_api" {
  filename         = "toll_api.zip"
  function_name    = "${var.project_name}-toll-api"
  role            = aws_iam_role.lambda_role.arn
  handler         = "lambda_function.lambda_handler"
  runtime         = "python3.9"
  timeout         = 10
  memory_size     = 128  # Minimum for free tier
  source_code_hash = filebase64sha256("toll_api.zip")

  environment {
    variables = {
      MODEL_S3_BUCKET = aws_s3_bucket.model_storage.bucket
      TRAFFIC_TABLE   = aws_dynamodb_table.traffic_data.name
      TOLL_TABLE      = aws_dynamodb_table.toll_history.name
    }
  }

  depends_on = [aws_iam_role_policy.lambda_policy]
}

# API Gateway (Free Tier: 1M API calls/month)
resource "aws_api_gateway_rest_api" "toll_api" {
  name        = "${var.project_name}-api"
  description = "Toll Pricing API"
}

resource "aws_api_gateway_resource" "toll" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  parent_id   = aws_api_gateway_rest_api.toll_api.root_resource_id
  path_part   = "toll"
}

resource "aws_api_gateway_method" "get_toll" {
  rest_api_id   = aws_api_gateway_rest_api.toll_api.id
  resource_id   = aws_api_gateway_resource.toll.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "toll_integration" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  resource_id = aws_api_gateway_resource.toll.id
  http_method = aws_api_gateway_method.get_toll.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.toll_api.invoke_arn
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.toll_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.toll_api.execution_arn}/*/*"
}

resource "aws_api_gateway_deployment" "toll_api_deployment" {
  depends_on = [aws_api_gateway_integration.toll_integration]
  
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
}

resource "aws_api_gateway_stage" "dev" {
  deployment_id = aws_api_gateway_deployment.toll_api_deployment.id
  rest_api_id   = aws_api_gateway_rest_api.toll_api.id
  stage_name    = "dev"
}

# Outputs
output "api_gateway_url" {
  description = "API Gateway URL"
  value       = "https://${aws_api_gateway_rest_api.toll_api.id}.execute-api.${var.aws_region}.amazonaws.com/${aws_api_gateway_stage.dev.stage_name}/toll"
}

output "dynamodb_tables" {
  description = "DynamoDB table names"
  value = {
    traffic = aws_dynamodb_table.traffic_data.name
    tolls   = aws_dynamodb_table.toll_history.name
  }
}