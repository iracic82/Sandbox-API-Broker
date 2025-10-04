"""Logging middleware for request/response tracking."""

import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging import log_request


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all requests and responses."""

    async def dispatch(self, request: Request, call_next):
        """Process request and log details."""
        # Generate request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Extract track ID from header if present
        track_id = request.headers.get("X-Track-ID")

        # Start timer
        start_time = time.time()

        # Process request
        try:
            response = await call_next(request)

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Determine outcome
            outcome = "success" if response.status_code < 400 else "failure"

            # Log request
            log_request(
                request_id=request_id,
                track_id=track_id,
                action=f"{request.method} {request.url.path}",
                outcome=outcome,
                latency_ms=latency_ms,
                message=f"{request.method} {request.url.path} - {response.status_code}",
            )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Log error
            log_request(
                request_id=request_id,
                track_id=track_id,
                action=f"{request.method} {request.url.path}",
                outcome="error",
                latency_ms=latency_ms,
                error=str(e),
                message=f"{request.method} {request.url.path} - Exception: {e}",
            )

            raise
