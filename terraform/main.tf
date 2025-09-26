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

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "tai-lam-traffic-simulator"
}

variable "environment" {
  description = "Environment"
  type        = string
  default     = "dev"
}

# DynamoDB Tables
resource "aws_dynamodb_table" "traffic_data" {
  name           = "${var.project_name}-traffic-data"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "timestamp"

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-traffic-data"
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "toll_history" {
  name           = "${var.project_name}-toll-history"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "timestamp"

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Name        = "${var.project_name}-toll-history"
    Environment = var.environment
  }
}

# Kinesis Data Stream
resource "aws_kinesis_stream" "traffic_stream" {
  name             = "${var.project_name}-traffic-stream"
  shard_count      = 1
  retention_period = 24

  shard_level_metrics = [
    "IncomingRecords",
    "OutgoingRecords",
  ]

  tags = {
    Name        = "${var.project_name}-traffic-stream"
    Environment = var.environment
  }
}

# IAM Role for Lambda
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

# IAM Policy for Lambda
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
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = [
          aws_dynamodb_table.traffic_data.arn,
          aws_dynamodb_table.toll_history.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kinesis:PutRecord",
          "kinesis:PutRecords",
          "kinesis:GetRecords",
          "kinesis:GetShardIterator",
          "kinesis:DescribeStream",
          "kinesis:ListStreams"
        ]
        Resource = aws_kinesis_stream.traffic_stream.arn
      }
    ]
  })
}

# Lambda function for toll pricing API
resource "aws_lambda_function" "toll_pricing_api" {
  filename         = "toll_pricing_api.zip"
  function_name    = "${var.project_name}-toll-pricing-api"
  role            = aws_iam_role.lambda_role.arn
  handler         = "toll_pricing_api.lambda_handler"
  runtime         = "python3.9"
  timeout         = 30

  environment {
    variables = {
      TRAFFIC_TABLE = aws_dynamodb_table.traffic_data.name
      TOLL_TABLE    = aws_dynamodb_table.toll_history.name
      KINESIS_STREAM = aws_kinesis_stream.traffic_stream.name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_policy,
    aws_cloudwatch_log_group.toll_pricing_logs,
  ]
}

# Lambda function for traffic ingestion
resource "aws_lambda_function" "traffic_ingestion" {
  filename         = "traffic_ingestion.zip"
  function_name    = "${var.project_name}-traffic-ingestion"
  role            = aws_iam_role.lambda_role.arn
  handler         = "traffic_ingestion.lambda_handler"
  runtime         = "python3.9"
  timeout         = 60

  environment {
    variables = {
      TRAFFIC_TABLE = aws_dynamodb_table.traffic_data.name
      TOLL_TABLE    = aws_dynamodb_table.toll_history.name
    }
  }

  depends_on = [
    aws_iam_role_policy.lambda_policy,
    aws_cloudwatch_log_group.traffic_ingestion_logs,
  ]
}

# CloudWatch Log Groups
resource "aws_cloudwatch_log_group" "toll_pricing_logs" {
  name              = "/aws/lambda/${var.project_name}-toll-pricing-api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "traffic_ingestion_logs" {
  name              = "/aws/lambda/${var.project_name}-traffic-ingestion"
  retention_in_days = 14
}

# Event Source Mapping for Kinesis
resource "aws_lambda_event_source_mapping" "kinesis_trigger" {
  event_source_arn  = aws_kinesis_stream.traffic_stream.arn
  function_name     = aws_lambda_function.traffic_ingestion.arn
  starting_position = "LATEST"
  batch_size        = 10
}

# API Gateway
resource "aws_api_gateway_rest_api" "toll_api" {
  name        = "${var.project_name}-api"
  description = "Tai Lam Traffic Simulator API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }
}

# API Gateway Resources
resource "aws_api_gateway_resource" "toll_resource" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  parent_id   = aws_api_gateway_rest_api.toll_api.root_resource_id
  path_part   = "toll"
}

resource "aws_api_gateway_resource" "current_resource" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  parent_id   = aws_api_gateway_resource.toll_resource.id
  path_part   = "current"
}

resource "aws_api_gateway_resource" "update_resource" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  parent_id   = aws_api_gateway_resource.toll_resource.id
  path_part   = "update"
}

resource "aws_api_gateway_resource" "history_resource" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  parent_id   = aws_api_gateway_resource.toll_resource.id
  path_part   = "history"
}

resource "aws_api_gateway_resource" "calculate_resource" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  parent_id   = aws_api_gateway_resource.toll_resource.id
  path_part   = "calculate"
}

# API Gateway Methods
resource "aws_api_gateway_method" "get_current_toll" {
  rest_api_id   = aws_api_gateway_rest_api.toll_api.id
  resource_id   = aws_api_gateway_resource.current_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "update_toll" {
  rest_api_id   = aws_api_gateway_rest_api.toll_api.id
  resource_id   = aws_api_gateway_resource.update_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "get_toll_history" {
  rest_api_id   = aws_api_gateway_rest_api.toll_api.id
  resource_id   = aws_api_gateway_resource.history_resource.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_method" "calculate_toll" {
  rest_api_id   = aws_api_gateway_rest_api.toll_api.id
  resource_id   = aws_api_gateway_resource.calculate_resource.id
  http_method   = "POST"
  authorization = "NONE"
}

# API Gateway Integrations
resource "aws_api_gateway_integration" "get_current_toll_integration" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  resource_id = aws_api_gateway_resource.current_resource.id
  http_method = aws_api_gateway_method.get_current_toll.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.toll_pricing_api.invoke_arn
}

resource "aws_api_gateway_integration" "update_toll_integration" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  resource_id = aws_api_gateway_resource.update_resource.id
  http_method = aws_api_gateway_method.update_toll.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.toll_pricing_api.invoke_arn
}

resource "aws_api_gateway_integration" "get_toll_history_integration" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  resource_id = aws_api_gateway_resource.history_resource.id
  http_method = aws_api_gateway_method.get_toll_history.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.toll_pricing_api.invoke_arn
}

resource "aws_api_gateway_integration" "calculate_toll_integration" {
  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  resource_id = aws_api_gateway_resource.calculate_resource.id
  http_method = aws_api_gateway_method.calculate_toll.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.toll_pricing_api.invoke_arn
}

# Lambda permissions for API Gateway
resource "aws_lambda_permission" "api_gateway_lambda" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.toll_pricing_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.toll_api.execution_arn}/*/*"
}

# API Gateway Deployment
resource "aws_api_gateway_deployment" "toll_api_deployment" {
  depends_on = [
    aws_api_gateway_integration.get_current_toll_integration,
    aws_api_gateway_integration.update_toll_integration,
    aws_api_gateway_integration.get_toll_history_integration,
    aws_api_gateway_integration.calculate_toll_integration,
  ]

  rest_api_id = aws_api_gateway_rest_api.toll_api.id
  stage_name  = var.environment
}

# Outputs
output "api_gateway_url" {
  description = "API Gateway URL"
  value       = "${aws_api_gateway_deployment.toll_api_deployment.invoke_url}"
}

output "dynamodb_traffic_table" {
  description = "DynamoDB Traffic Data Table Name"
  value       = aws_dynamodb_table.traffic_data.name
}

output "dynamodb_toll_table" {
  description = "DynamoDB Toll History Table Name"
  value       = aws_dynamodb_table.toll_history.name
}

output "kinesis_stream_name" {
  description = "Kinesis Stream Name"
  value       = aws_kinesis_stream.traffic_stream.name
}

output "lambda_toll_pricing_function" {
  description = "Lambda Toll Pricing Function Name"
  value       = aws_lambda_function.toll_pricing_api.function_name
}

output "lambda_traffic_ingestion_function" {
  description = "Lambda Traffic Ingestion Function Name"
  value       = aws_lambda_function.traffic_ingestion.function_name
}