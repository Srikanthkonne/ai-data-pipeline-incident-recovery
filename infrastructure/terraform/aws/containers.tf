resource "aws_ecr_repository" "api" {
  name                 = "${local.resource_prefix}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_repository" "worker" {
  name                 = "${local.resource_prefix}-worker"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${local.resource_prefix}/api"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${local.resource_prefix}/worker"
  retention_in_days = 14
}

resource "aws_cloudwatch_log_group" "migration" {
  name              = "/ecs/${local.resource_prefix}/migration"
  retention_in_days = 14
}

resource "aws_ecs_cluster" "platform" {
  name = "${local.resource_prefix}-cluster"
}

data "aws_iam_policy_document" "ecs_task_assume_role" {
  statement {
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }

    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "ecs_execution" {
  name               = "IncidentRecoveryECSExecutionRole"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "IncidentRecoveryECSSecrets"
  role = aws_iam_role.ecs_execution.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "ReadRuntimeSecrets"
        Effect = "Allow"
        Action = "secretsmanager:GetSecretValue"
        Resource = [
          aws_db_instance.platform.master_user_secret[0].secret_arn,
          aws_secretsmanager_secret.gemini_api_key.arn,
        ]
      },
    ]
  })
}

resource "aws_iam_role" "api_task" {
  name               = "IncidentRecoveryAPITaskRole"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
}

resource "aws_iam_role" "worker_task" {
  name               = "IncidentRecoveryWorkerTaskRole"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume_role.json
}

resource "aws_iam_role_policy" "worker_cloud_recovery" {
  name = "IncidentRecoveryWorkerCloudRecovery"
  role = aws_iam_role.worker_task.name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "RecoveryArtifacts"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
        ]
        Resource = "${aws_s3_bucket.recovery.arn}/*"
      },
      {
        Sid    = "RecoveryBucket"
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:ListBucket",
        ]
        Resource = aws_s3_bucket.recovery.arn
      },
      {
        Sid      = "StartEMRServerlessRecoveryJob"
        Effect   = "Allow"
        Action   = "emr-serverless:StartJobRun"
        Resource = aws_emrserverless_application.recovery.arn
      },
      {
        Sid    = "ManageEMRServerlessRecoveryJob"
        Effect = "Allow"
        Action = [
          "emr-serverless:GetJobRun",
          "emr-serverless:CancelJobRun",
        ]
        Resource = "${aws_emrserverless_application.recovery.arn}/jobruns/*"
      },
      {
        Sid      = "PassEMRRuntimeRole"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = aws_iam_role.emr_runtime.arn

        Condition = {
          StringEquals = {
            "iam:PassedToService" = "emr-serverless.amazonaws.com"
          }
        }
      },
    ]
  })
}
