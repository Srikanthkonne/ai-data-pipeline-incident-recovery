resource "aws_emrserverless_application" "recovery" {
  name          = var.emr_application_name
  release_label = var.emr_release_label
  type          = "spark"
  architecture  = "X86_64"

  auto_start_configuration {
    enabled = true
  }

  auto_stop_configuration {
    enabled              = true
    idle_timeout_minutes = 5
  }

  maximum_capacity {
    cpu    = "8 vCPU"
    memory = "32 GB"
    disk   = "400000 GB"
  }

  monitoring_configuration {
    managed_persistence_monitoring_configuration {
      enabled = true
    }
  }

  scheduler_configuration {
    queue_timeout_minutes = 360
    max_concurrent_runs   = 15
  }

  lifecycle {
    prevent_destroy = true
  }
}
