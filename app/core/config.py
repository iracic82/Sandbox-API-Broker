"""Application configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    # API Configuration
    broker_api_token: str = "dev_token_change_me"
    broker_admin_token: str = "admin_token_change_me"
    api_base_path: str = "/v1"

    # DynamoDB Configuration
    ddb_table_name: str = "SandboxPool"
    ddb_gsi1_name: str = "StatusIndex"
    ddb_gsi2_name: str = "TrackIndex"
    ddb_gsi3_name: str = "IdempotencyIndex"
    ddb_endpoint_url: str | None = None  # For local DynamoDB
    aws_region: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None

    # Sandbox Lifecycle
    lab_duration_hours: int = 4
    grace_period_minutes: int = 30
    sync_interval_sec: int = 600
    cleanup_interval_sec: int = 300
    cleanup_batch_size: int = 10  # Process N sandboxes per batch
    cleanup_batch_delay_sec: float = 2.0  # Delay between batches (throttling)
    auto_expiry_interval_sec: int = 300

    # ENG CSP Integration
    csp_base_url: str = "https://csp.infoblox.com/v2"
    csp_api_token: str = ""
    csp_timeout_connect_sec: int = 5
    csp_timeout_read_sec: int = 15  # DELETE operations can take 5-10 seconds

    # Concurrency & Resilience
    k_candidates: int = 15
    backoff_base_ms: int = 100
    backoff_max_ms: int = 5000
    deletion_retry_max_attempts: int = 3
    circuit_breaker_threshold: int = 5
    circuit_breaker_timeout_sec: int = 60

    # Observability
    log_level: str = "INFO"
    log_format: str = "json"
    metrics_port: int = 9090
    enable_request_id: bool = True

    # CORS Configuration
    cors_allowed_origins: str = "*"  # Comma-separated list, e.g., "https://app1.com,https://app2.com"

    @property
    def lab_duration_seconds(self) -> int:
        """Get lab duration in seconds."""
        return self.lab_duration_hours * 3600

    @property
    def expiry_threshold_seconds(self) -> int:
        """Get expiry threshold (lab duration + grace period) in seconds."""
        return self.lab_duration_seconds + (self.grace_period_minutes * 60)


# Global settings instance
settings = Settings()
