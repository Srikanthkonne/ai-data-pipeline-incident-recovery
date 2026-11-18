locals {
  monitoring_namespace = "IncidentRecovery/${var.environment}"
}

resource "aws_cloudwatch_log_metric_filter" "recovery_resolved" {
  name           = "${local.resource_prefix}-recovery-resolved"
  log_group_name = aws_cloudwatch_log_group.worker.name

  pattern = "\"RESOLVED\""

  metric_transformation {
    name          = "RecoveryResolvedCount"
    namespace     = local.monitoring_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "rca_failed" {
  name           = "${local.resource_prefix}-rca-failed"
  log_group_name = aws_cloudwatch_log_group.worker.name

  pattern = "\"RCA_FAILED\""

  metric_transformation {
    name          = "RCAFailedCount"
    namespace     = local.monitoring_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "policy_failed" {
  name           = "${local.resource_prefix}-policy-failed"
  log_group_name = aws_cloudwatch_log_group.worker.name

  pattern = "\"POLICY_FAILED\""

  metric_transformation {
    name          = "PolicyFailedCount"
    namespace     = local.monitoring_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "execution_failed" {
  name           = "${local.resource_prefix}-execution-failed"
  log_group_name = aws_cloudwatch_log_group.worker.name

  pattern = "\"EXECUTION_FAILED\""

  metric_transformation {
    name          = "ExecutionFailedCount"
    namespace     = local.monitoring_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "validation_error" {
  name           = "${local.resource_prefix}-validation-error"
  log_group_name = aws_cloudwatch_log_group.worker.name

  pattern = "\"VALIDATION_ERROR\""

  metric_transformation {
    name          = "ValidationErrorCount"
    namespace     = local.monitoring_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "validation_failed" {
  name           = "${local.resource_prefix}-validation-failed"
  log_group_name = aws_cloudwatch_log_group.worker.name

  pattern = "\"VALIDATION_FAILED\""

  metric_transformation {
    name          = "ValidationFailedCount"
    namespace     = local.monitoring_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "worker_error" {
  name           = "${local.resource_prefix}-worker-error"
  log_group_name = aws_cloudwatch_log_group.worker.name

  pattern = "\"WORKER_ERROR\""

  metric_transformation {
    name          = "WorkerErrorCount"
    namespace     = local.monitoring_namespace
    value         = "1"
    default_value = "0"
  }
}

resource "aws_cloudwatch_log_metric_filter" "claim_lost" {
  name           = "${local.resource_prefix}-claim-lost"
  log_group_name = aws_cloudwatch_log_group.worker.name

  pattern = "\"CLAIM_LOST\""

  metric_transformation {
    name          = "ClaimLostCount"
    namespace     = local.monitoring_namespace
    value         = "1"
    default_value = "0"
  }
}
