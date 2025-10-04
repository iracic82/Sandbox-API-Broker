/**
 * AWS Secrets Manager for sensitive configuration
 */

resource "aws_secretsmanager_secret" "broker_api_token" {
  name_prefix             = "${var.app_name}-broker-api-token-"
  description             = "Sandbox Broker API token for track authentication"
  recovery_window_in_days = 7

  tags = {
    Name = "${var.app_name}-broker-api-token"
  }
}

resource "aws_secretsmanager_secret_version" "broker_api_token" {
  secret_id     = aws_secretsmanager_secret.broker_api_token.id
  secret_string = var.broker_api_token
}

resource "aws_secretsmanager_secret" "broker_admin_token" {
  name_prefix             = "${var.app_name}-broker-admin-token-"
  description             = "Sandbox Broker admin token for admin endpoints"
  recovery_window_in_days = 7

  tags = {
    Name = "${var.app_name}-broker-admin-token"
  }
}

resource "aws_secretsmanager_secret_version" "broker_admin_token" {
  secret_id     = aws_secretsmanager_secret.broker_admin_token.id
  secret_string = var.broker_admin_token
}

resource "aws_secretsmanager_secret" "csp_api_token" {
  name_prefix             = "${var.app_name}-csp-api-token-"
  description             = "Infoblox CSP API token"
  recovery_window_in_days = 7

  tags = {
    Name = "${var.app_name}-csp-api-token"
  }
}

resource "aws_secretsmanager_secret_version" "csp_api_token" {
  secret_id     = aws_secretsmanager_secret.csp_api_token.id
  secret_string = var.csp_api_token
}
