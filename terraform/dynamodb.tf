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

  hash_key = "PK"

  # Primary Key
  attribute {
    name = "PK"
    type = "S"
  }

  # GSI1: StatusIndex (status + sandbox_id)
  attribute {
    name = "GSI1PK"
    type = "S"
  }

  attribute {
    name = "GSI1SK"
    type = "S"
  }

  # GSI2: TrackIndex (allocated_to_track)
  attribute {
    name = "GSI2PK"
    type = "S"
  }

  # GSI3: IdempotencyIndex (idempotency_key)
  attribute {
    name = "GSI3PK"
    type = "S"
  }

  # GSI1: StatusIndex - Query sandboxes by status
  global_secondary_index {
    name            = "StatusIndex"
    hash_key        = "GSI1PK"
    range_key       = "GSI1SK"
    projection_type = "ALL"

    # Only needed for PROVISIONED billing mode
    # read_capacity  = var.ddb_read_capacity
    # write_capacity = var.ddb_write_capacity
  }

  # GSI2: TrackIndex - Query sandboxes by track_id
  global_secondary_index {
    name            = "TrackIndex"
    hash_key        = "GSI2PK"
    projection_type = "ALL"

    # Only needed for PROVISIONED billing mode
    # read_capacity  = var.ddb_read_capacity
    # write_capacity = var.ddb_write_capacity
  }

  # GSI3: IdempotencyIndex - Query by idempotency key
  global_secondary_index {
    name            = "IdempotencyIndex"
    hash_key        = "GSI3PK"
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
