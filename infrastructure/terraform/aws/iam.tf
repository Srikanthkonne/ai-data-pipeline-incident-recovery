resource "aws_iam_role" "emr_runtime" {
  name        = var.emr_runtime_role_name
  description = "EMR Serverless runtime role for incident recovery Phase 5B"

  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "AllowEMRServerlessAssumeRole"
        Effect = "Allow"

        Principal = {
          Service = "emr-serverless.amazonaws.com"
        }

        Action = "sts:AssumeRole"

        Condition = {
          StringEquals = {
            "aws:SourceAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role_policy" "emr_runtime_s3" {
  name = "IncidentRecoveryS3Access"
  role = aws_iam_role.emr_runtime.name

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ProjectBucketAccess"
        Effect = "Allow"

        Action = [
          "s3:ListBucket",
          "s3:GetBucketLocation",
        ]

        Resource = aws_s3_bucket.recovery.arn
      },
      {
        Sid    = "ProjectObjectAccess"
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
        ]

        Resource = "${aws_s3_bucket.recovery.arn}/*"
      }
    ]
  })
}
