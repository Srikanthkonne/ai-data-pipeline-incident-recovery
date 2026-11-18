locals {
  api_image    = "${aws_ecr_repository.api.repository_url}:${var.container_image_tag}"
  worker_image = "${aws_ecr_repository.worker.repository_url}:${var.container_image_tag}"

  database_secret_arn = aws_db_instance.platform.master_user_secret[0].secret_arn

  common_database_environment = [
    {
      name  = "POSTGRES_HOST"
      value = aws_db_instance.platform.address
    },
    {
      name  = "POSTGRES_PORT"
      value = "5432"
    },
    {
      name  = "POSTGRES_DB"
      value = aws_db_instance.platform.db_name
    },
  ]

  common_database_secrets = [
    {
      name      = "POSTGRES_USER"
      valueFrom = "${local.database_secret_arn}:username::"
    },
    {
      name      = "POSTGRES_PASSWORD"
      valueFrom = "${local.database_secret_arn}:password::"
    },
  ]

  worker_environment = concat(
    local.common_database_environment,
    [
      {
        name  = "AWS_REGION"
        value = var.aws_region
      },
      {
        name  = "RECOVERY_EXECUTION_BACKEND"
        value = "emr-serverless"
      },
      {
        name  = "RECOVERY_STORAGE_BACKEND"
        value = "aws-s3"
      },
      {
        name  = "EMR_SERVERLESS_APPLICATION_ID"
        value = aws_emrserverless_application.recovery.id
      },
      {
        name  = "EMR_SERVERLESS_EXECUTION_ROLE_ARN"
        value = aws_iam_role.emr_runtime.arn
      },
      {
        name  = "EMR_SERVERLESS_ARTIFACT_BUCKET"
        value = aws_s3_bucket.recovery.id
      },
      {
        name  = "EMR_SERVERLESS_ARTIFACT_PREFIX"
        value = "incident-recovery"
      },
      {
        name  = "RECOVERY_SILVER_PATH"
        value = "s3://${aws_s3_bucket.recovery.id}/silver/transactions"
      },
      {
        name  = "RECOVERY_BACKUP_PATH"
        value = "s3://${aws_s3_bucket.recovery.id}/failure-backups/schema-drift/silver-transactions"
      },
      {
        name  = "RECOVERY_TEMP_PATH"
        value = "s3://${aws_s3_bucket.recovery.id}/failure-temp/schema-drift-restore/silver-transactions"
      },
      {
        name  = "RECOVERY_SCHEMA_EVIDENCE_PATH"
        value = "s3://${aws_s3_bucket.recovery.id}/evidence/silver_schema.json"
      },
      {
        name  = "RECOVERY_DATASET_NAMESPACE"
        value = "s3://${aws_s3_bucket.recovery.id}"
      },
      {
        name  = "RECOVERY_DATASET_NAME"
        value = "silver/transactions"
      },
      {
        name  = "INCIDENT_WORKER_DRY_RUN"
        value = "false"
      },
      {
        name  = "INCIDENT_WORKER_POLL_INTERVAL_SECONDS"
        value = "10"
      },
      {
        name  = "INCIDENT_WORKER_MAX_INCIDENTS_PER_CYCLE"
        value = "1"
      },
      {
        name  = "INCIDENT_WORKER_MAX_AUTONOMOUS_ATTEMPTS"
        value = "3"
      },
      {
        name  = "INCIDENT_WORKER_QUEUE_CLAIM_SECONDS"
        value = "300"
      },
      {
        name  = "INCIDENT_WORKER_QUEUE_HEARTBEAT_INTERVAL_SECONDS"
        value = "60"
      },
      {
        name  = "INCIDENT_WORKER_RETRY_BASE_SECONDS"
        value = "60"
      },
      {
        name  = "INCIDENT_WORKER_RETRY_MAX_SECONDS"
        value = "1800"
      },
    ]
  )
}

resource "aws_lb" "api" {
  name               = "incident-recovery-${var.environment}-alb"
  internal           = false
  load_balancer_type = "application"

  security_groups = [
    aws_security_group.alb.id,
  ]

  subnets = [
    aws_subnet.public_a.id,
    aws_subnet.public_b.id,
  ]
}

resource "aws_lb_target_group" "api" {
  name        = "incident-recovery-${var.environment}-api"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.platform.id

  health_check {
    enabled             = true
    path                = "/ready"
    protocol            = "HTTP"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "api_http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

resource "aws_ecs_task_definition" "api" {
  family                   = "${local.resource_prefix}-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.api_task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = local.api_image
      essential = true

      portMappings = [
        {
          containerPort = 8000
          hostPort      = 8000
          protocol      = "tcp"
        }
      ]

      environment = local.common_database_environment
      secrets     = local.common_database_secrets

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.api.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "api"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${local.resource_prefix}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = "512"
  memory = "1024"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.worker_task.arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = local.worker_image
      essential = true

      environment = local.worker_environment

      secrets = concat(
        local.common_database_secrets,
        [
          {
            name      = "GEMINI_API_KEY"
            valueFrom = aws_secretsmanager_secret.gemini_api_key.arn
          }
        ]
      )

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.worker.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "worker"
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "migration" {
  family                   = "${local.resource_prefix}-migration"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"

  cpu    = "256"
  memory = "512"

  execution_role_arn = aws_iam_role.ecs_execution.arn
  task_role_arn      = aws_iam_role.api_task.arn

  container_definitions = jsonencode([
    {
      name      = "migration"
      image     = local.api_image
      essential = true

      command = [
        "python",
        "-m",
        "incident_service.db_migrate",
      ]

      environment = local.common_database_environment
      secrets     = local.common_database_secrets

      logConfiguration = {
        logDriver = "awslogs"

        options = {
          awslogs-group         = aws_cloudwatch_log_group.migration.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "migration"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "api" {
  name            = "${local.resource_prefix}-api"
  cluster         = aws_ecs_cluster.platform.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  health_check_grace_period_seconds = 60

  network_configuration {
    subnets = [
      aws_subnet.public_a.id,
      aws_subnet.public_b.id,
    ]

    security_groups = [
      aws_security_group.ecs.id,
    ]

    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  depends_on = [
    aws_lb_listener.api_http,
    aws_iam_role_policy_attachment.ecs_execution_managed,
    aws_iam_role_policy.ecs_execution_secrets,
  ]
}

resource "aws_ecs_service" "worker" {
  name            = "${local.resource_prefix}-worker"
  cluster         = aws_ecs_cluster.platform.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets = [
      aws_subnet.public_a.id,
      aws_subnet.public_b.id,
    ]

    security_groups = [
      aws_security_group.ecs.id,
    ]

    assign_public_ip = true
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecs_execution_managed,
    aws_iam_role_policy.ecs_execution_secrets,
    aws_iam_role_policy.worker_cloud_recovery,
  ]
}
