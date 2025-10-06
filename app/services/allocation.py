"""Sandbox allocation service with concurrency handling."""

import time
import random
from typing import Optional
from app.core.config import settings
from app.db.dynamodb import db_client
from app.models.sandbox import Sandbox, SandboxStatus
from app.core.metrics import (
    allocate_total,
    allocate_idempotent_hits,
    allocate_conflicts,
    deletion_marked_total,
    allocation_latency,
)


class AllocationError(Exception):
    """Base exception for allocation errors."""

    pass


class NoSandboxesAvailableError(AllocationError):
    """Raised when no sandboxes are available."""

    pass


class NotSandboxOwnerError(AllocationError):
    """Raised when track doesn't own the sandbox."""

    pass


class AllocationExpiredError(AllocationError):
    """Raised when allocation has expired."""

    pass


class AllocationService:
    """Service for handling sandbox allocation and deallocation."""

    def __init__(self):
        self.db = db_client

    async def allocate_sandbox(
        self,
        track_id: str,
        idempotency_key: Optional[str] = None,
        instruqt_track_id: Optional[str] = None,
        name_prefix: Optional[str] = None,
    ) -> Sandbox:
        """
        Allocate a sandbox to an Instruqt sandbox instance with idempotency and retry logic.

        Args:
            track_id: The unique Instruqt sandbox ID (per-student instance, not lab identifier)
            idempotency_key: Optional idempotency key (uses track_id if not provided)
            instruqt_track_id: Optional lab/track identifier (for grouping and analytics)
            name_prefix: Optional sandbox name prefix filter (e.g., "lab-adventure")

        Returns:
            Allocated Sandbox

        Raises:
            NoSandboxesAvailableError: No sandboxes available after retries
        """
        start_time = time.time()
        current_time = int(start_time)
        idem_key = idempotency_key or track_id

        try:
            # Step 1: Check for existing allocation (idempotency)
            existing = await self.db.find_allocation_by_idempotency_key(idem_key)
            if existing and not existing.is_expired(current_time, settings.grace_period_minutes):
                # Return existing allocation if still valid
                allocate_idempotent_hits.inc()
                allocate_total.labels(outcome="idempotent").inc()
                allocation_latency.labels(outcome="idempotent").observe(time.time() - start_time)
                return existing

            # Step 2: K-candidate fan-out strategy (with optional name filtering)
            candidates = await self.db.get_available_candidates(
                k=settings.k_candidates,
                name_prefix=name_prefix
            )

            if not candidates:
                allocate_total.labels(outcome="no_sandboxes").inc()
                allocation_latency.labels(outcome="no_sandboxes").observe(time.time() - start_time)
                raise NoSandboxesAvailableError("No sandboxes available in pool")

            # Step 3: Try to allocate with exponential backoff
            max_attempts = len(candidates)
            conflicts = 0

            for attempt, candidate in enumerate(candidates):
                sandbox = await self.db.atomic_allocate(
                    sandbox_id=candidate.sandbox_id,
                    track_id=track_id,
                    idempotency_key=idem_key,
                    current_time=current_time,
                    track_name=instruqt_track_id,
                )

                if sandbox:
                    # Success! Return allocated sandbox
                    allocate_total.labels(outcome="success").inc()
                    allocation_latency.labels(outcome="success").observe(time.time() - start_time)
                    if conflicts > 0:
                        allocate_conflicts.inc(conflicts)
                    return sandbox

                # Conflict - another track claimed this sandbox
                conflicts += 1

                # Apply jitter backoff before next attempt
                if attempt < max_attempts - 1:
                    jitter = random.uniform(0, min(2 ** attempt * settings.backoff_base_ms, settings.backoff_max_ms))
                    await self._sleep_ms(jitter)

            # Exhausted all candidates
            allocate_total.labels(outcome="no_sandboxes").inc()
            allocate_conflicts.inc(conflicts)
            allocation_latency.labels(outcome="no_sandboxes").observe(time.time() - start_time)
            raise NoSandboxesAvailableError(
                f"Failed to allocate after {max_attempts} attempts (high contention)"
            )
        except NoSandboxesAvailableError:
            raise
        except Exception as e:
            allocate_total.labels(outcome="error").inc()
            allocation_latency.labels(outcome="error").observe(time.time() - start_time)
            raise

    async def mark_for_deletion(
        self,
        sandbox_id: str,
        track_id: str,
    ) -> Sandbox:
        """
        Mark sandbox for deletion with ownership validation.

        Args:
            sandbox_id: The sandbox ID to mark
            track_id: The track requesting deletion

        Returns:
            Updated Sandbox

        Raises:
            NotSandboxOwnerError: Track doesn't own sandbox
            AllocationExpiredError: Allocation already expired
        """
        current_time = int(time.time())

        # Calculate max valid expiry time (allocated_at must be > this to be valid)
        max_expiry_time = current_time - settings.lab_duration_seconds

        try:
            sandbox = await self.db.mark_for_deletion(
                sandbox_id=sandbox_id,
                track_id=track_id,
                current_time=current_time,
                max_expiry_time=max_expiry_time,
            )

            if not sandbox:
                # Condition failed - check why
                existing = await self.db.get_sandbox(sandbox_id)

                if not existing:
                    deletion_marked_total.labels(outcome="not_found").inc()
                    raise NotSandboxOwnerError(f"Sandbox {sandbox_id} not found")

                if existing.status != SandboxStatus.ALLOCATED:
                    deletion_marked_total.labels(outcome="not_allocated").inc()
                    raise NotSandboxOwnerError(
                        f"Sandbox {sandbox_id} status is {existing.status.value}, not allocated"
                    )

                if existing.allocated_to_track != track_id:
                    deletion_marked_total.labels(outcome="not_owner").inc()
                    raise NotSandboxOwnerError(
                        f"Sandbox {sandbox_id} is owned by {existing.allocated_to_track}, not {track_id}"
                    )

                # Must be expired
                deletion_marked_total.labels(outcome="expired").inc()
                raise AllocationExpiredError(
                    f"Sandbox {sandbox_id} allocation expired (allocated at {existing.allocated_at})"
                )

            deletion_marked_total.labels(outcome="success").inc()
            return sandbox
        except (NotSandboxOwnerError, AllocationExpiredError):
            raise
        except Exception as e:
            deletion_marked_total.labels(outcome="error").inc()
            raise

    async def get_sandbox(self, sandbox_id: str, track_id: str) -> Sandbox:
        """
        Get sandbox details (track must own it).

        Args:
            sandbox_id: The sandbox ID
            track_id: The requesting track

        Returns:
            Sandbox details

        Raises:
            NotSandboxOwnerError: Track doesn't own sandbox
        """
        sandbox = await self.db.get_sandbox(sandbox_id)

        if not sandbox:
            raise NotSandboxOwnerError(f"Sandbox {sandbox_id} not found")

        if not sandbox.is_owned_by(track_id):
            raise NotSandboxOwnerError(
                f"Sandbox {sandbox_id} is not owned by track {track_id}"
            )

        return sandbox

    async def _sleep_ms(self, milliseconds: float):
        """Sleep for given milliseconds (async-safe)."""
        import asyncio
        await asyncio.sleep(milliseconds / 1000.0)


# Global allocation service instance
allocation_service = AllocationService()
