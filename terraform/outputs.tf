/**
 * Terraform Outputs
 */

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_url" {
  description = "URL to access the API"
  value       = var.enable_https ? "https://${aws_lb.main.dns_name}" : "http://${aws_lb.main.dns_name}"
}

output "api_endpoint" {
  description = "Full API endpoint URL"
  value       = var.enable_https ? "https://${aws_lb.main.dns_name}/v1" : "http://${aws_lb.main.dns_name}/v1"
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.app.name
}

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.sandbox_pool.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.sandbox_pool.arn
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.app.name
}

output "secrets_broker_api_token_arn" {
  description = "ARN of the broker API token secret"
  value       = aws_secretsmanager_secret.broker_api_token.arn
}

output "secrets_broker_admin_token_arn" {
  description = "ARN of the broker admin token secret"
  value       = aws_secretsmanager_secret.broker_admin_token.arn
}

output "secrets_csp_api_token_arn" {
  description = "ARN of the CSP API token secret"
  value       = aws_secretsmanager_secret.csp_api_token.arn
  sensitive   = true
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "private_subnet_ids" {
  description = "IDs of the private subnets"
  value       = aws_subnet.private[*].id
}

output "public_subnet_ids" {
  description = "IDs of the public subnets"
  value       = aws_subnet.public[*].id
}
