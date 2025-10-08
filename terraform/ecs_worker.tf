/**
 * ECS Worker Service - Background Jobs
 *
 * Runs background jobs (sync, cleanup, auto-expiry) separately from API service.
 * This prevents duplicate job execution when running multiple API instances for HA.
 */

# Worker Task Definition
resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.project_name}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name  = "${var.project_name}-worker"
      image = "${aws_ecr_repository.sandbox_broker_api.repository_url}:latest"

      # Override command to run worker instead of API
      command = ["python", "-m", "app.jobs.worker"]

      essential = true

      environment = [
        {
          name  = "BROKER_API_TOKEN"
          value = var.broker_api_token
        },
        {
          name  = "BROKER_ADMIN_TOKEN"
          value = var.broker_admin_token
        },
        {
          name  = "DDB_TABLE_NAME"
          value = aws_dynamodb_table.sandbox_pool.name
        },
        {
          name  = "DDB_GSI1_NAME"
          value = "StatusIndex"
        },
        {
          name  = "DDB_GSI2_NAME"
          value = "TrackIndex"
        },
        {
          name  = "DDB_GSI3_NAME"
          value = "IdempotencyIndex"
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "CSP_BASE_URL"
          value = var.csp_base_url
        },
        {
          name  = "CSP_API_TOKEN"
          value = var.csp_api_token
        },
        {
          name  = "LOG_LEVEL"
          value = "INFO"
        },
        {
          name  = "SYNC_INTERVAL_SEC"
          value = "600"
        },
        {
          name  = "CLEANUP_INTERVAL_SEC"
          value = "300"
        },
        {
          name  = "AUTO_EXPIRY_INTERVAL_SEC"
          value = "300"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }

      # Health check not needed for worker (no HTTP server)
    }
  ])

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-worker-task"
  })
}

# Worker CloudWatch Log Group
resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.project_name}-worker"
  retention_in_days = var.log_retention_days

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-worker-logs"
  })
}

# Worker ECS Service (single task, no load balancer)
resource "aws_ecs_service" "worker" {
  name            = "${var.project_name}-worker"
  cluster         = aws_ecs_cluster.sandbox_broker.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = 1  # Only 1 worker needed (no HA required for background jobs)
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  # No load balancer needed (worker doesn't serve HTTP traffic)

  # Deployment configuration
  deployment_minimum_healthy_percent = 0    # Allow stopping old task before starting new one
  deployment_maximum_percent         = 100  # Only run 1 task at a time

  # Enable ECS Exec for debugging
  enable_execute_command = true

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-worker-service"
  })

  depends_on = [
    aws_iam_role_policy_attachment.ecs_execution_role_policy,
    aws_iam_role_policy_attachment.ecs_task_role_dynamodb,
  ]
}

# CloudWatch Alarms for Worker
resource "aws_cloudwatch_metric_alarm" "worker_cpu_high" {
  alarm_name          = "${var.project_name}-worker-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Worker CPU usage is too high"
  alarm_actions       = []  # Add SNS topic ARN if you want notifications

  dimensions = {
    ClusterName = aws_ecs_cluster.sandbox_broker.name
    ServiceName = aws_ecs_service.worker.name
  }

  tags = var.common_tags
}

resource "aws_cloudwatch_metric_alarm" "worker_memory_high" {
  alarm_name          = "${var.project_name}-worker-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Worker memory usage is too high"
  alarm_actions       = []  # Add SNS topic ARN if you want notifications

  dimensions = {
    ClusterName = aws_ecs_cluster.sandbox_broker.name
    ServiceName = aws_ecs_service.worker.name
  }

  tags = var.common_tags
}

# Outputs
output "worker_service_name" {
  description = "Name of the worker ECS service"
  value       = aws_ecs_service.worker.name
}

output "worker_log_group" {
  description = "CloudWatch log group for worker"
  value       = aws_cloudwatch_log_group.worker.name
}
