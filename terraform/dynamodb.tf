/**
 * DynamoDB Table with Global Secondary Indexes
 */

resource "aws_dynamodb_table" "sandbox_pool" {
  name         = "${var.app_name}-pool"
  billing_mode = "PAY_PER_REQUEST" # On-demand pricing for unpredictable workloads

  # Alternative: Provisioned capacity with auto-scaling
  # billing_mode   = "PROVISIONED"
  # read_capacity  = var.ddb_read_capacity
  # write_capacity = var.ddb_write_capacity

  hash_key  = "PK"
  range_key = "SK"

  # Primary Key
  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  # GSI attributes (using actual data attributes, not projection keys)
  attribute {
    name = "status"
    type = "S"
  }

  attribute {
    name = "allocated_at"
    type = "N"
  }

  attribute {
    name = "allocated_to_track"
    type = "S"
  }

  attribute {
    name = "idempotency_key"
    type = "S"
  }

  # GSI1: StatusIndex - Query sandboxes by status
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "status"
    range_key       = "allocated_at"
    projection_type = "ALL"

    # Only needed for PROVISIONED billing mode
    # read_capacity  = var.ddb_read_capacity
    # write_capacity = var.ddb_write_capacity
  }

  # GSI2: TrackIndex - Query sandboxes by track_id
  global_secondary_index {
    name            = "TrackIndex"
    hash_key        = "allocated_to_track"
    range_key       = "allocated_at"
    projection_type = "ALL"

    # Only needed for PROVISIONED billing mode
    # read_capacity  = var.ddb_read_capacity
    # write_capacity = var.ddb_write_capacity
  }

  # GSI3: IdempotencyIndex - Query by idempotency key
  global_secondary_index {
    name            = "IdempotencyIndex"
    hash_key        = "idempotency_key"
    range_key       = "allocated_at"
    projection_type = "ALL"

    # Only needed for PROVISIONED billing mode
    # read_capacity  = var.ddb_read_capacity
    # write_capacity = var.ddb_write_capacity
  }

  # Point-in-time recovery for data protection
  point_in_time_recovery {
    enabled = true
  }

  # Server-side encryption
  server_side_encryption {
    enabled = true
  }

  # TTL for automatic expiry (optional, we handle via jobs)
  ttl {
    attribute_name = "ttl"
    enabled        = false
  }

  tags = {
    Name = "${var.app_name}-dynamodb-table"
  }
}

# Auto-scaling for PROVISIONED billing mode (optional)
# Uncomment if using billing_mode = "PROVISIONED"

# resource "aws_appautoscaling_target" "dynamodb_table_read" {
#   max_capacity       = var.ddb_read_capacity * 10
#   min_capacity       = var.ddb_read_capacity
#   resource_id        = "table/${aws_dynamodb_table.sandbox_pool.name}"
#   scalable_dimension = "dynamodb:table:ReadCapacityUnits"
#   service_namespace  = "dynamodb"
# }

# resource "aws_appautoscaling_policy" "dynamodb_table_read_policy" {
#   name               = "${var.app_name}-dynamodb-read-autoscaling"
#   policy_type        = "TargetTrackingScaling"
#   resource_id        = aws_appautoscaling_target.dynamodb_table_read.resource_id
#   scalable_dimension = aws_appautoscaling_target.dynamodb_table_read.scalable_dimension
#   service_namespace  = aws_appautoscaling_target.dynamodb_table_read.service_namespace

#   target_tracking_scaling_policy_configuration {
#     predefined_metric_specification {
#       predefined_metric_type = "DynamoDBReadCapacityUtilization"
#     }
#     target_value = 70.0
#   }
# }
