resource "aws_iam_role_policy" "provisioner_cloudwatch_log_read" {
  name = "IncidentRecoveryProvisionerCloudWatchLogRead"
  role = "IncidentRecoveryProvisioner"

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ReadIncidentRecoveryECSLogs"
        Effect = "Allow"

        Action = [
          "logs:GetLogEvents",
        ]

        Resource = [
          "arn:aws:logs:us-east-1:275956876816:log-group:/ecs/ai-data-pipeline-incident-recovery-dev/*:*",
        ]
      },
    ]
  })
}
