/**
 * ECS Fargate Cluster and Service
 */

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.app_name}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.app_name}-cluster"
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "app" {
  family                   = var.app_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ecs_task_cpu
  memory                   = var.ecs_task_memory
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = var.app_name
      image     = var.container_image
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "API_BASE_PATH"
          value = "/v1"
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
          name  = "LOG_LEVEL"
          value = "INFO"
        },
        {
          name  = "LOG_FORMAT"
          value = "json"
        }
      ]

      secrets = [
        {
          name      = "BROKER_API_TOKEN"
          valueFrom = aws_secretsmanager_secret.broker_api_token.arn
        },
        {
          name      = "BROKER_ADMIN_TOKEN"
          valueFrom = aws_secretsmanager_secret.broker_admin_token.arn
        },
        {
          name      = "CSP_API_TOKEN"
          valueFrom = aws_secretsmanager_secret.csp_api_token.arn
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.app.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:${var.container_port}/healthz || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.app_name}-task"
  }
}

# ECS Service
resource "aws_ecs_service" "app" {
  name            = var.app_name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.ecs_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = var.app_name
    container_port   = var.container_port
  }

  health_check_grace_period_seconds = 120

  # Deployment configuration
  deployment_maximum_percent         = 200
  deployment_minimum_healthy_percent = 100

  # Enable service deployment circuit breaker
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  # Ensure ALB is created before service
  depends_on = [
    aws_lb_listener.http,
    aws_iam_role_policy.ecs_dynamodb
  ]

  tags = {
    Name = "${var.app_name}-service"
  }
}

# Auto-scaling target
resource "aws_appautoscaling_target" "ecs" {
  max_capacity       = var.ecs_autoscaling_max
  min_capacity       = var.ecs_autoscaling_min
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.app.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Auto-scaling policy: CPU utilization
resource "aws_appautoscaling_policy" "ecs_cpu" {
  name               = "${var.app_name}-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value       = 70.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}

# Auto-scaling policy: Memory utilization
resource "aws_appautoscaling_policy" "ecs_memory" {
  name               = "${var.app_name}-memory-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageMemoryUtilization"
    }
    target_value       = 80.0
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
