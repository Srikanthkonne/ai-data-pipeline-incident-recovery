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
          "iam:AttachRolePolicy",
          "iam:CreateRole",
          "iam:DeleteRole",
          "iam:DeleteRolePolicy",
          "iam:DetachRolePolicy",
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

        Resource = [
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.runtime_role_name}",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.ecs_execution_role_name}",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.api_task_role_name}",
          "arn:aws:iam::${data.aws_caller_identity.current.account_id}:role/${var.worker_task_role_name}",
        ]
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
        Sid    = "PlatformNetworking"
        Effect = "Allow"

        Action = [
          "ec2:AssociateRouteTable",
          "ec2:AttachInternetGateway",
          "ec2:AuthorizeSecurityGroupEgress",
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:CreateInternetGateway",
          "ec2:CreateRoute",
          "ec2:CreateRouteTable",
          "ec2:CreateSecurityGroup",
          "ec2:CreateSubnet",
          "ec2:CreateTags",
          "ec2:CreateVpc",
          "ec2:DeleteInternetGateway",
          "ec2:DeleteRoute",
          "ec2:DeleteRouteTable",
          "ec2:DeleteSecurityGroup",
          "ec2:DeleteSubnet",
          "ec2:DeleteTags",
          "ec2:DeleteVpc",
          "ec2:Describe*",
          "ec2:GetSecurityGroupsForVpc",
          "ec2:DetachInternetGateway",
          "ec2:DisassociateRouteTable",
          "ec2:ModifySubnetAttribute",
          "ec2:ModifyVpcAttribute",
          "ec2:ReplaceRoute",
          "ec2:ReplaceRouteTableAssociation",
          "ec2:RevokeSecurityGroupEgress",
          "ec2:RevokeSecurityGroupIngress",
        ]

        Resource = "*"
      },
      {
        Sid    = "ContainerRegistry"
        Effect = "Allow"

        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:BatchGetImage",
          "ecr:CompleteLayerUpload",
          "ecr:CreateRepository",
          "ecr:DeleteRepository",
          "ecr:DescribeImages",
          "ecr:DescribeRepositories",
          "ecr:GetAuthorizationToken",
          "ecr:GetDownloadUrlForLayer",
          "ecr:GetLifecyclePolicy",
          "ecr:GetRepositoryPolicy",
          "ecr:InitiateLayerUpload",
          "ecr:ListImages",
          "ecr:ListTagsForResource",
          "ecr:PutImage",
          "ecr:PutImageScanningConfiguration",
          "ecr:PutImageTagMutability",
          "ecr:TagResource",
          "ecr:UntagResource",
          "ecr:UploadLayerPart",
        ]

        Resource = "*"
      },
      {
        Sid    = "ECSPlatform"
        Effect = "Allow"

        Action = [
          "ecs:CreateCluster",
          "ecs:CreateService",
          "ecs:DeleteCluster",
          "ecs:DeleteService",
          "ecs:DeregisterTaskDefinition",
          "ecs:DescribeClusters",
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:ListServices",
          "ecs:ListTagsForResource",
          "ecs:ListTaskDefinitions",
          "ecs:ListTasks",
          "ecs:DescribeTasks",
          "ecs:RegisterTaskDefinition",
          "ecs:RunTask",
          "ecs:StopTask",
          "ecs:TagResource",
          "ecs:UntagResource",
          "ecs:UpdateService",
        ]

        Resource = "*"
      },
      {
        Sid    = "RDSAndSecretsKMS"
        Effect = "Allow"

        Action = [
          "kms:CreateGrant",
          "kms:Decrypt",
          "kms:DescribeKey",
          "kms:Encrypt",
          "kms:GenerateDataKey",
          "kms:ReEncryptFrom",
          "kms:ReEncryptTo",
        ]

        Resource = "*"
      },
      {
        Sid    = "RDSPlatform"
        Effect = "Allow"

        Action = [
          "rds:AddTagsToResource",
          "rds:CreateDBInstance",
          "rds:CreateDBSubnetGroup",
          "rds:DeleteDBInstance",
          "rds:DeleteDBSubnetGroup",
          "rds:Describe*",
          "rds:ListTagsForResource",
          "rds:ModifyDBInstance",
          "rds:ModifyDBSubnetGroup",
          "rds:RemoveTagsFromResource",
        ]

        Resource = "*"
      },
      {
        Sid    = "LoadBalancing"
        Effect = "Allow"

        Action = [
          "elasticloadbalancing:AddTags",
          "elasticloadbalancing:CreateListener",
          "elasticloadbalancing:CreateLoadBalancer",
          "elasticloadbalancing:CreateTargetGroup",
          "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:DeleteTargetGroup",
          "elasticloadbalancing:Describe*",
          "elasticloadbalancing:ModifyListener",
          "elasticloadbalancing:ModifyLoadBalancerAttributes",
          "elasticloadbalancing:ModifyTargetGroup",
          "elasticloadbalancing:ModifyTargetGroupAttributes",
          "elasticloadbalancing:RemoveTags",
          "elasticloadbalancing:SetIpAddressType",
          "elasticloadbalancing:SetSecurityGroups",
          "elasticloadbalancing:SetSubnets",
        ]

        Resource = "*"
      },
      {
        Sid    = "ApplicationSecrets"
        Effect = "Allow"

        Action = [
          "secretsmanager:CreateSecret",
          "secretsmanager:DeleteSecret",
          "secretsmanager:DescribeSecret",
          "secretsmanager:GetResourcePolicy",
          "secretsmanager:ListSecretVersionIds",
          "secretsmanager:ListSecrets",
          "secretsmanager:PutSecretValue",
          "secretsmanager:RestoreSecret",
          "secretsmanager:TagResource",
          "secretsmanager:UntagResource",
        ]

        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"

        Action = [
          "logs:CreateLogGroup",
          "logs:DeleteLogGroup",
          "logs:DeleteRetentionPolicy",
          "logs:DescribeLogGroups",
          "logs:DescribeMetricFilters",
          "logs:DeleteMetricFilter",
          "logs:PutMetricFilter",
          "logs:ListTagsForResource",
          "logs:PutRetentionPolicy",
          "logs:TagResource",
          "logs:UntagResource",
        ]

        Resource = "*"
      },
      {
        Sid      = "PlatformServiceLinkedRoles"
        Effect   = "Allow"
        Action   = "iam:CreateServiceLinkedRole"
        Resource = "*"

        Condition = {
          StringEquals = {
            "iam:AWSServiceName" = [
              "ecs.amazonaws.com",
              "rds.amazonaws.com",
              "elasticloadbalancing.amazonaws.com",
            ]
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
