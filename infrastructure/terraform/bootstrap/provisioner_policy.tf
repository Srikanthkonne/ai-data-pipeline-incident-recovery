resource "aws_iam_role_policy" "provisioner" {
  name = "IncidentRecoveryProvisionerPolicy"
  role = aws_iam_role.provisioner.name

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "ProjectS3Bucket"
        Effect = "Allow"

        Action = [
          "s3:CreateBucket",
          "s3:DeleteBucket",
          "s3:GetAccelerateConfiguration",
          "s3:GetBucketAcl",
          "s3:GetBucketCORS",
          "s3:GetBucketLocation",
          "s3:GetBucketLogging",
          "s3:GetBucketObjectLockConfiguration",
          "s3:GetBucketPolicy",
          "s3:GetBucketPublicAccessBlock",
          "s3:GetBucketRequestPayment",
          "s3:GetBucketTagging",
          "s3:GetBucketVersioning",
          "s3:GetBucketWebsite",
          "s3:GetEncryptionConfiguration",
          "s3:GetLifecycleConfiguration",
          "s3:GetObjectLockConfiguration",
          "s3:GetReplicationConfiguration",
          "s3:ListBucket",
          "s3:ListTagsForResource",
          "s3:PutBucketPublicAccessBlock",
          "s3:PutBucketTagging",
          "s3:PutEncryptionConfiguration",
        ]

        Resource = "arn:aws:s3:::${var.project_bucket_name}"
      },
      {
        Sid    = "ProjectS3Objects"
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
        ]

        Resource = "arn:aws:s3:::${var.project_bucket_name}/*"
      },
      {
        Sid    = "EMRServerless"
        Effect = "Allow"

        Action = [
          "emr-serverless:CancelJobRun",
          "emr-serverless:CreateApplication",
          "emr-serverless:DeleteApplication",
          "emr-serverless:GetApplication",
          "emr-serverless:GetJobRun",
          "emr-serverless:ListApplications",
          "emr-serverless:ListJobRuns",
          "emr-serverless:ListTagsForResource",
          "emr-serverless:StartApplication",
          "emr-serverless:StartJobRun",
          "emr-serverless:StopApplication",
          "emr-serverless:TagResource",
          "emr-serverless:UntagResource",
          "emr-serverless:UpdateApplication",
        ]

        Resource = "*"
      },
      {
        Sid    = "RuntimeRoleManagement"
        Effect = "Allow"

        Action = [
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:DeleteRolePolicy",
          "iam:GetRole",
          "iam:GetRolePolicy",
          "iam:ListAttachedRolePolicies",
          "iam:ListRolePolicies",
          "iam:ListRoleTags",
          "iam:PassRole",
          "iam:PutRolePolicy",
          "iam:TagRole",
          "iam:UntagRole",
          "iam:UpdateAssumeRolePolicy",
          "iam:UpdateRole",
          "iam:UpdateRoleDescription",
        ]

        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.runtime_role_name}"
      },
      {
        Sid      = "EMRServiceLinkedRole"
        Effect   = "Allow"
        Action   = "iam:CreateServiceLinkedRole"
        Resource = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/aws-service-role/ops.emr-serverless.amazonaws.com/AWSServiceRoleForAmazonEMRServerless*"

        Condition = {
          StringEquals = {
            "iam:AWSServiceName" = "ops.emr-serverless.amazonaws.com"
          }
        }
      },
      {
        Sid    = "TerraformStateBucket"
        Effect = "Allow"

        Action = [
          "s3:CreateBucket",
          "s3:GetBucketLocation",
          "s3:ListBucket",
          "s3:GetBucketVersioning",
          "s3:PutBucketVersioning",
          "s3:GetEncryptionConfiguration",
          "s3:PutEncryptionConfiguration",
          "s3:GetBucketPublicAccessBlock",
          "s3:PutBucketPublicAccessBlock",
          "s3:GetBucketTagging",
          "s3:PutBucketTagging",
        ]

        Resource = "arn:aws:s3:::${var.terraform_state_bucket_name}"
      },
      {
        Sid    = "TerraformStateObjects"
        Effect = "Allow"

        Action = [
          "s3:GetObject",
          "s3:PutObject",
        ]

        Resource = [
          "arn:aws:s3:::${var.terraform_state_bucket_name}/phase5c/terraform.tfstate",
          "arn:aws:s3:::${var.terraform_state_bucket_name}/phase5c/terraform.tfstate.tflock",
          "arn:aws:s3:::${var.terraform_state_bucket_name}/bootstrap/terraform.tfstate",
          "arn:aws:s3:::${var.terraform_state_bucket_name}/bootstrap/terraform.tfstate.tflock",
        ]
      },
      {
        Sid    = "TerraformStateLockDelete"
        Effect = "Allow"
        Action = "s3:DeleteObject"
        Resource = [
          "arn:aws:s3:::${var.terraform_state_bucket_name}/phase5c/terraform.tfstate.tflock",
          "arn:aws:s3:::${var.terraform_state_bucket_name}/bootstrap/terraform.tfstate.tflock",
        ]
      },
    ]
  })
}
