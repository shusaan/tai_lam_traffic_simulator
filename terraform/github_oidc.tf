# GitHub OIDC Provider
resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = [
    "sts.amazonaws.com",
  ]

  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd"
  ]

  tags = {
    Name = "github-actions-oidc"
  }
}

# IAM Role for GitHub Actions
resource "aws_iam_role" "github_actions" {
  name = "github-actions-tai-lam-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRole"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:shussan/tai_lam_traffic_simulator:*"
          }
        }
      }
    ]
  })

  tags = {
    Name = "github-actions-role"
  }
}

# Policy for GitHub Actions (ECS deployment only)
resource "aws_iam_policy" "github_actions_policy" {
  name = "github-actions-ecs-deploy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid = "ECSDeployment"
        Effect = "Allow"
        Action = [
          "ecs:DescribeTaskDefinition",
          "ecs:RegisterTaskDefinition",
          "ecs:UpdateService",
          "ecs:DescribeServices"
        ]
        Resource = [
          "arn:aws:ecs:${var.aws_region}:*:task-definition/${var.project_name}-task:*",
          "arn:aws:ecs:${var.aws_region}:*:service/${var.project_name}-cluster/${var.project_name}-service"
        ]
      },
      {
        Sid = "ECSClusterAccess"
        Effect = "Allow"
        Action = [
          "ecs:DescribeClusters"
        ]
        Resource = [
          "arn:aws:ecs:${var.aws_region}:*:cluster/${var.project_name}-cluster"
        ]
      },
      {
        Sid = "IAMPassRole"
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution_role.arn,
          aws_iam_role.ecs_task_role.arn
        ]
      }
    ]
  })
}

# Attach policy to role
resource "aws_iam_role_policy_attachment" "github_actions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions_policy.arn
}

# Output role ARN for GitHub Actions
output "github_actions_role_arn" {
  description = "IAM Role ARN for GitHub Actions OIDC"
  value       = aws_iam_role.github_actions.arn
}