variable "aws_region" {
  description = "AWS region used by the incident recovery platform."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Base name used for AWS resources."
  type        = string
  default     = "ai-data-pipeline-incident-recovery"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"
}

variable "artifact_bucket_name" {
  description = "S3 bucket used for recovery datasets, scripts, evidence, and logs."
  type        = string
  default     = "ai-data-pipeline-incident-recovery-275956876816-us-east-1"
}

variable "emr_application_name" {
  description = "Name of the EMR Serverless recovery application."
  type        = string
  default     = "incident-recovery-phase5b"
}

variable "emr_release_label" {
  description = "EMR release used by the recovery application."
  type        = string
  default     = "emr-7.13.0"
}

variable "emr_runtime_role_name" {
  description = "IAM role assumed by EMR Serverless recovery jobs."
  type        = string
  default     = "IncidentRecoveryEMRRuntimeRole"
}

variable "terraform_execution_role_arn" {
  description = "IAM role assumed by Terraform for AWS infrastructure management."
  type        = string
  default     = "arn:aws:iam::275956876816:role/IncidentRecoveryProvisioner"
}


variable "container_image_tag" {
  description = "Container image tag deployed to ECS."
  type        = string
  default     = "latest"
}

variable "api_desired_count" {
  description = "Desired number of API ECS tasks."
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "Desired number of autonomous recovery worker ECS tasks."
  type        = number
  default     = 1
}

variable "api_allowed_cidr" {
  description = "IPv4 CIDR allowed to reach the public API load balancer."
  type        = string
  default     = "127.0.0.1/32"
}
