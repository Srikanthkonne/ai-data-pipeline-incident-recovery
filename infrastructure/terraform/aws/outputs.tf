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
