"""Rate limiting middleware using token bucket algorithm."""

import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.core.config import settings


class TokenBucket:
    """Token bucket for rate limiting."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed, False if rate limit exceeded
        """
        now = time.time()

        # Refill tokens based on time elapsed
        elapsed = now - self.last_refill
        refill_amount = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + refill_amount)
        self.last_refill = now

        # Try to consume
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_retry_after(self) -> int:
        """Get seconds until next token is available."""
        if self.tokens >= 1:
            return 0
        tokens_needed = 1 - self.tokens
        return int(tokens_needed / self.refill_rate) + 1


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware with per-client token buckets.

    Uses X-Instruqt-Sandbox-ID or X-Track-ID header or client IP for identification.
    Implements token bucket algorithm for smooth rate limiting.
    """

    def __init__(self, app, requests_per_second: int = 10, burst: int = 20):
        """
        Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_second: Sustained rate limit
            burst: Maximum burst capacity
        """
        super().__init__(app)
        self.requests_per_second = requests_per_second
        self.burst = burst
        self.buckets: Dict[str, TokenBucket] = defaultdict(
            lambda: TokenBucket(capacity=burst, refill_rate=requests_per_second)
        )
        self.last_cleanup = time.time()

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""

        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/healthz", "/readyz", "/metrics"]:
            return await call_next(request)

        # Identify client (prefer X-Instruqt-Sandbox-ID, fallback to X-Track-ID, then IP)
        client_id = request.headers.get("X-Instruqt-Sandbox-ID")
        if not client_id:
            client_id = request.headers.get("X-Track-ID")
        if not client_id:
            client_id = request.client.host if request.client else "unknown"

        # Get or create bucket for this client
        bucket = self.buckets[client_id]

        # Try to consume a token
        if not bucket.consume(1):
            retry_after = bucket.get_retry_after()
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Rate limit exceeded for client {client_id}",
                        "retry_after": retry_after,
                    }
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.requests_per_second),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = int(bucket.tokens)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_second)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        # Periodic cleanup of idle buckets (every 5 minutes)
        now = time.time()
        if now - self.last_cleanup > 300:
            self._cleanup_buckets()
            self.last_cleanup = now

        return response

    def _cleanup_buckets(self):
        """Remove buckets that haven't been used recently."""
        now = time.time()
        idle_threshold = 600  # 10 minutes

        # Find idle clients
        idle_clients = [
            client_id
            for client_id, bucket in self.buckets.items()
            if now - bucket.last_refill > idle_threshold
        ]

        # Remove idle buckets
        for client_id in idle_clients:
            del self.buckets[client_id]

        if idle_clients:
            print(f"[RateLimit] Cleaned up {len(idle_clients)} idle buckets")
