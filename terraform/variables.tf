/**
 * Terraform Variables
 */

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "prod"
}

variable "app_name" {
  description = "Application name"
  type        = string
  default     = "sandbox-broker"
}

# VPC Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Availability zones for subnets"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

# ECS Configuration
variable "ecs_task_cpu" {
  description = "ECS task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 1024
}

variable "ecs_task_memory" {
  description = "ECS task memory in MB"
  type        = number
  default     = 2048
}

variable "ecs_desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_autoscaling_min" {
  description = "Minimum number of ECS tasks"
  type        = number
  default     = 2
}

variable "ecs_autoscaling_max" {
  description = "Maximum number of ECS tasks"
  type        = number
  default     = 10
}

# Worker Configuration
variable "worker_cpu" {
  description = "CPU units for worker task (256, 512, 1024, etc.)"
  type        = number
  default     = 256
}

variable "worker_memory" {
  description = "Memory (MB) for worker task"
  type        = number
  default     = 512
}

# Container Configuration
variable "container_image" {
  description = "Docker image URI (ECR or Docker Hub)"
  type        = string
  default     = "sandbox-broker-api:latest"
}

variable "container_port" {
  description = "Container port"
  type        = number
  default     = 8080
}

# DynamoDB Configuration
variable "ddb_read_capacity" {
  description = "DynamoDB read capacity units (for provisioned billing)"
  type        = number
  default     = 50
}

variable "ddb_write_capacity" {
  description = "DynamoDB write capacity units (for provisioned billing)"
  type        = number
  default     = 50
}

# Application Configuration
variable "broker_api_token" {
  description = "API token for track authentication (store in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "broker_admin_token" {
  description = "Admin token for admin endpoints (store in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "csp_api_token" {
  description = "Infoblox CSP API token (store in Secrets Manager)"
  type        = string
  sensitive   = true
}

variable "csp_base_url" {
  description = "Infoblox CSP API base URL"
  type        = string
  default     = "https://csp.infoblox.com/v2"
}

# ALB Configuration
variable "certificate_arn" {
  description = "ACM certificate ARN for HTTPS (optional)"
  type        = string
  default     = ""
}

variable "enable_https" {
  description = "Enable HTTPS listener (requires certificate_arn)"
  type        = bool
  default     = false
}

# Monitoring
variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# Background Jobs Schedule
variable "sync_schedule" {
  description = "EventBridge schedule for sync job (cron)"
  type        = string
  default     = "rate(10 minutes)"
}

variable "cleanup_schedule" {
  description = "EventBridge schedule for cleanup job (cron)"
  type        = string
  default     = "rate(5 minutes)"
}

variable "auto_expiry_schedule" {
  description = "EventBridge schedule for auto-expiry job (cron)"
  type        = string
  default     = "rate(5 minutes)"
}
