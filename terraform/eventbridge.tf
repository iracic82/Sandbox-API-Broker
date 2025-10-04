/**
 * EventBridge Scheduler for Background Jobs
 *
 * Note: Background jobs are currently handled by in-process threads in the FastAPI app.
 * This configuration is for future migration to EventBridge-triggered ECS tasks.
 *
 * To enable EventBridge-based jobs:
 * 1. Create separate ECS task definitions for each job type
 * 2. Update the target configurations below with the correct task ARNs
 * 3. Modify the FastAPI app to disable in-process background jobs
 */

# Sync Job Schedule (fetch sandboxes from CSP)
resource "aws_scheduler_schedule" "sync_job" {
  name       = "${var.app_name}-sync-job"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = var.sync_schedule

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.app.arn
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = aws_subnet.private[*].id
        security_groups  = [aws_security_group.ecs_tasks.id]
        assign_public_ip = false
      }
    }

    # Pass job type as environment variable override
    input = jsonencode({
      containerOverrides = [
        {
          name = var.app_name
          environment = [
            {
              name  = "JOB_TYPE"
              value = "sync"
            }
          ]
        }
      ]
    })
  }

  # Disable by default (jobs run in-process)
  state = "DISABLED"
}

# Cleanup Job Schedule (delete pending_deletion sandboxes)
resource "aws_scheduler_schedule" "cleanup_job" {
  name       = "${var.app_name}-cleanup-job"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = var.cleanup_schedule

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.app.arn
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = aws_subnet.private[*].id
        security_groups  = [aws_security_group.ecs_tasks.id]
        assign_public_ip = false
      }
    }

    input = jsonencode({
      containerOverrides = [
        {
          name = var.app_name
          environment = [
            {
              name  = "JOB_TYPE"
              value = "cleanup"
            }
          ]
        }
      ]
    })
  }

  # Disable by default (jobs run in-process)
  state = "DISABLED"
}

# Auto-Expiry Job Schedule (expire allocated sandboxes after 4.5h)
resource "aws_scheduler_schedule" "auto_expiry_job" {
  name       = "${var.app_name}-auto-expiry-job"
  group_name = "default"

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression = var.auto_expiry_schedule

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.eventbridge_scheduler.arn

    ecs_parameters {
      task_definition_arn = aws_ecs_task_definition.app.arn
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = aws_subnet.private[*].id
        security_groups  = [aws_security_group.ecs_tasks.id]
        assign_public_ip = false
      }
    }

    input = jsonencode({
      containerOverrides = [
        {
          name = var.app_name
          environment = [
            {
              name  = "JOB_TYPE"
              value = "auto-expiry"
            }
          ]
        }
      ]
    })
  }

  # Disable by default (jobs run in-process)
  state = "DISABLED"
}
