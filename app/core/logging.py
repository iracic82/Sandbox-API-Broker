"""Structured JSON logging configuration."""

import logging
import sys
import json
from datetime import datetime
from typing import Any, Dict
from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id
        if hasattr(record, "track_id"):
            log_data["track_id"] = record.track_id
        if hasattr(record, "sandbox_id"):
            log_data["sandbox_id"] = record.sandbox_id
        if hasattr(record, "action"):
            log_data["action"] = record.action
        if hasattr(record, "outcome"):
            log_data["outcome"] = record.outcome
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, "error"):
            log_data["error"] = record.error
        if hasattr(record, "instruqt_track_id"):
            log_data["instruqt_track_id"] = record.instruqt_track_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging():
    """Configure application logging."""
    # Create logger
    logger = logging.getLogger("sandbox_broker")
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Remove existing handlers
    logger.handlers = []

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter based on config
    if settings.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )

    logger.addHandler(handler)

    return logger


# Global logger instance
logger = setup_logging()


def log_request(
    request_id: str,
    track_id: str = None,
    sandbox_id: str = None,
    action: str = None,
    outcome: str = None,
    latency_ms: int = None,
    error: str = None,
    message: str = None,
    instruqt_track_id: str = None,
):
    """
    Log structured request information.

    Args:
        request_id: Unique request identifier
        track_id: Track ID if applicable (Instruqt sandbox ID)
        sandbox_id: Sandbox ID if applicable
        action: Action performed (allocate, delete, sync, etc.)
        outcome: Outcome (success, failure, conflict, etc.)
        latency_ms: Request latency in milliseconds
        error: Error message if failed
        message: Log message
        instruqt_track_id: Optional Instruqt track/lab ID for analytics
    """
    extra = {
        "request_id": request_id,
    }

    if track_id:
        extra["track_id"] = track_id
    if sandbox_id:
        extra["sandbox_id"] = sandbox_id
    if action:
        extra["action"] = action
    if outcome:
        extra["outcome"] = outcome
    if latency_ms is not None:
        extra["latency_ms"] = latency_ms
    if error:
        extra["error"] = error
    if instruqt_track_id:
        extra["instruqt_track_id"] = instruqt_track_id

    if outcome == "failure" or error:
        logger.error(message or f"Request failed: {action}", extra=extra)
    else:
        logger.info(message or f"Request completed: {action}", extra=extra)
