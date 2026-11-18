variable "aws_region" {
  description = "AWS region used by the incident recovery platform."
  type        = string
  default     = "us-east-1"
}

variable "bootstrap_user_name" {
  description = "IAM user used for authenticated local bootstrap access."
  type        = string
  default     = "IncidentRecoveryBootstrap"
}

variable "provisioner_role_name" {
  description = "IAM role assumed by Terraform for infrastructure provisioning."
  type        = string
  default     = "IncidentRecoveryProvisioner"
}

variable "runtime_role_name" {
  description = "EMR Serverless runtime IAM role managed by the application Terraform stack."
  type        = string
  default     = "IncidentRecoveryEMRRuntimeRole"
}

variable "project_bucket_name" {
  description = "Primary incident recovery S3 bucket."
  type        = string
  default     = "ai-data-pipeline-incident-recovery-275956876816-us-east-1"
}

variable "terraform_state_bucket_name" {
  description = "Dedicated Terraform remote-state S3 bucket."
  type        = string
  default     = "incident-recovery-tfstate-275956876816-us-east-1"
}

variable "ecs_execution_role_name" {
  description = "ECS task execution IAM role managed by the application Terraform stack."
  type        = string
  default     = "IncidentRecoveryECSExecutionRole"
}

variable "api_task_role_name" {
  description = "ECS task IAM role used by the incident recovery API."
  type        = string
  default     = "IncidentRecoveryAPITaskRole"
}

variable "worker_task_role_name" {
  description = "ECS task IAM role used by the autonomous recovery worker."
  type        = string
  default     = "IncidentRecoveryWorkerTaskRole"
}
