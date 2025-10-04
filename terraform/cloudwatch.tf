/**
 * CloudWatch Log Groups
 */

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.app_name}"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.app_name}-logs"
  }
}

resource "aws_cloudwatch_log_group" "background_jobs" {
  name              = "/ecs/${var.app_name}-background-jobs"
  retention_in_days = var.log_retention_days

  tags = {
    Name = "${var.app_name}-background-jobs-logs"
  }
}
