provider "aws" {
  region = var.aws_region

  assume_role {
    role_arn     = var.terraform_execution_role_arn
    session_name = "incident-recovery-terraform"
  }

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

locals {
  resource_prefix = "${var.project_name}-${var.environment}"
}

data "aws_caller_identity" "current" {}
