resource "aws_iam_user" "bootstrap" {
  name = var.bootstrap_user_name
  path = "/"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_role" "provisioner" {
  name                 = var.provisioner_role_name
  path                 = "/"
  description          = "Terraform provisioner for the incident recovery platform"
  max_session_duration = 3600

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          AWS = aws_iam_user.bootstrap.arn
        }

        Action = "sts:AssumeRole"
      }
    ]
  })

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_iam_user_policy" "bootstrap_assume_provisioner" {
  name = "AssumeIncidentRecoveryProvisioner"
  user = aws_iam_user.bootstrap.name

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect   = "Allow"
        Action   = "sts:AssumeRole"
        Resource = aws_iam_role.provisioner.arn
      }
    ]
  })
}

resource "aws_iam_user_policy_attachment" "bootstrap_signin_local_development" {
  user       = aws_iam_user.bootstrap.name
  policy_arn = "arn:aws:iam::aws:policy/SignInLocalDevelopmentAccess"
}
