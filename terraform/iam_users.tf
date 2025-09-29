# IAM User for GitHub Actions deployment
resource "aws_iam_user" "tailam_deployer" {
  name = "tailam_deployer"
  path = "/"

  tags = {
    Name = "Tai Lam Deployer"
    Purpose = "GitHub Actions ECS deployment"
  }
}

# Access keys for GitHub Actions
resource "aws_iam_access_key" "tailam_deployer" {
  user = aws_iam_user.tailam_deployer.name
}

# IAM Policy for ECS deployment with minimal permissions
resource "aws_iam_policy" "tailam_deployer_policy" {
  name        = "TaiLamDeployerPolicy"
  description = "Minimal permissions for ECS deployment from GitHub Actions"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ECSTaskManagement"
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
        Sid    = "ECSClusterAccess"
        Effect = "Allow"
        Action = [
          "ecs:DescribeClusters"
        ]
        Resource = [
          "arn:aws:ecs:${var.aws_region}:*:cluster/${var.project_name}-cluster"
        ]
      },
      {
        Sid    = "IAMPassRole"
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

# Attach policy to user
resource "aws_iam_user_policy_attachment" "tailam_deployer" {
  user       = aws_iam_user.tailam_deployer.name
  policy_arn = aws_iam_policy.tailam_deployer_policy.arn
}

# Outputs for GitHub Actions secrets
output "tailam_deployer_access_key" {
  description = "Access key for GitHub Actions"
  value       = aws_iam_access_key.tailam_deployer.id
}

output "tailam_deployer_secret_key" {
  description = "Secret key for GitHub Actions (sensitive)"
  value       = aws_iam_access_key.tailam_deployer.secret
  sensitive   = true
}