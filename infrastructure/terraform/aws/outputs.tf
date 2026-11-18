output "aws_region" {
  description = "AWS region for the incident recovery platform."
  value       = var.aws_region
}

output "artifact_bucket_name" {
  description = "S3 bucket used by the incident recovery platform."
  value       = aws_s3_bucket.recovery.id
}

output "artifact_bucket_arn" {
  description = "ARN of the incident recovery S3 bucket."
  value       = aws_s3_bucket.recovery.arn
}

output "emr_serverless_application_id" {
  description = "EMR Serverless application ID used for cloud recovery execution."
  value       = aws_emrserverless_application.recovery.id
}

output "emr_serverless_application_arn" {
  description = "ARN of the EMR Serverless application."
  value       = aws_emrserverless_application.recovery.arn
}

output "emr_runtime_role_arn" {
  description = "IAM runtime role assumed by EMR Serverless jobs."
  value       = aws_iam_role.emr_runtime.arn
}

output "recovery_execution_environment" {
  description = "Non-secret environment values consumed by the recovery service."
  value = {
    AWS_REGION                        = var.aws_region
    RECOVERY_EXECUTION_BACKEND        = "emr-serverless"
    RECOVERY_STORAGE_BACKEND          = "aws-s3"
    EMR_SERVERLESS_APPLICATION_ID     = aws_emrserverless_application.recovery.id
    EMR_SERVERLESS_EXECUTION_ROLE_ARN = aws_iam_role.emr_runtime.arn
    EMR_SERVERLESS_ARTIFACT_BUCKET    = aws_s3_bucket.recovery.id
    EMR_SERVERLESS_ARTIFACT_PREFIX    = "incident-recovery"
  }
}


output "api_load_balancer_dns_name" {
  description = "DNS name of the incident recovery API load balancer."
  value       = aws_lb.api.dns_name
}

output "api_ecr_repository_url" {
  description = "ECR repository URL for the API image."
  value       = aws_ecr_repository.api.repository_url
}

output "worker_ecr_repository_url" {
  description = "ECR repository URL for the worker image."
  value       = aws_ecr_repository.worker.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster running the cloud control plane."
  value       = aws_ecs_cluster.platform.name
}

output "migration_task_definition_arn" {
  description = "Task definition used for one-off PostgreSQL schema migrations."
  value       = aws_ecs_task_definition.migration.arn
}

output "gemini_secret_arn" {
  description = "Secrets Manager secret that stores the Gemini API key."
  value       = aws_secretsmanager_secret.gemini_api_key.arn
}

output "database_address" {
  description = "Private RDS PostgreSQL hostname."
  value       = aws_db_instance.platform.address
}
