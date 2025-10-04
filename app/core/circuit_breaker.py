"""Circuit breaker pattern for external service calls."""

import time
from enum import Enum
from typing import Callable, Any, Optional
from app.core.config import settings


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker for external service calls.

    Prevents cascade failures by stopping requests to failing services.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout_seconds: int = 60,
        name: str = "default",
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Failures before opening circuit
            timeout_seconds: Seconds to wait before trying again
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.name = name

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.success_count = 0

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call function with circuit breaker protection (sync version).

        Args:
            func: Function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                print(f"[CircuitBreaker:{self.name}] Attempting reset (HALF_OPEN)")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                # Circuit is open, reject request
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service unavailable. Retry after {self._get_retry_after()}s"
                )

        # Try to call the function
        try:
            result = func(*args, **kwargs)

            # Success! Record it
            self._on_success()
            return result

        except Exception as e:
            # Failure! Record it
            self._on_failure()
            raise

    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Call async function with circuit breaker protection.

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        # Check if circuit should transition from OPEN to HALF_OPEN
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                print(f"[CircuitBreaker:{self.name}] Attempting reset (HALF_OPEN)")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                # Circuit is open, reject request
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN. "
                    f"Service unavailable. Retry after {self._get_retry_after()}s"
                )

        # Try to call the async function
        try:
            result = await func(*args, **kwargs)

            # Success! Record it
            self._on_success()
            return result

        except Exception as e:
            # Failure! Record it
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try resetting."""
        if self.last_failure_time is None:
            return True
        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.timeout_seconds

    def _on_success(self):
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            # Success in HALF_OPEN state, close the circuit
            print(f"[CircuitBreaker:{self.name}] Service recovered, closing circuit")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def _on_failure(self):
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery attempt, back to OPEN
            print(f"[CircuitBreaker:{self.name}] Recovery failed, opening circuit again")
            self.state = CircuitState.OPEN

        elif self.state == CircuitState.CLOSED:
            # Check if we've hit the failure threshold
            if self.failure_count >= self.failure_threshold:
                print(
                    f"[CircuitBreaker:{self.name}] Failure threshold reached "
                    f"({self.failure_count}/{self.failure_threshold}), opening circuit"
                )
                self.state = CircuitState.OPEN

    def _get_retry_after(self) -> int:
        """Get seconds until circuit might close."""
        if self.last_failure_time is None:
            return 0
        elapsed = time.time() - self.last_failure_time
        remaining = max(0, self.timeout_seconds - elapsed)
        return int(remaining)

    def get_state(self) -> dict:
        """Get current circuit breaker state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "timeout_seconds": self.timeout_seconds,
            "last_failure_time": self.last_failure_time,
        }


# Global circuit breaker for ENG CSP service
eng_csp_circuit_breaker = CircuitBreaker(
    failure_threshold=settings.circuit_breaker_threshold,
    timeout_seconds=settings.circuit_breaker_timeout_sec,
    name="eng_csp",
)
