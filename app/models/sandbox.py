"""Sandbox domain models."""

from enum import Enum
from typing import Optional
from datetime import datetime


class SandboxStatus(str, Enum):
    """Sandbox status enum."""

    AVAILABLE = "available"
    ALLOCATED = "allocated"
    PENDING_DELETION = "pending_deletion"
    STALE = "stale"
    DELETION_FAILED = "deletion_failed"


class Sandbox:
    """Sandbox domain model."""

    def __init__(
        self,
        sandbox_id: str,
        name: str,
        external_id: str,
        status: SandboxStatus,
        allocated_to_track: Optional[str] = None,
        allocated_at: Optional[int] = None,
        lab_duration_hours: int = 4,
        deletion_requested_at: Optional[int] = None,
        deletion_retry_count: int = 0,
        last_synced: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        track_name: Optional[str] = None,
        created_at: Optional[int] = None,
        updated_at: Optional[int] = None,
    ):
        self.sandbox_id = sandbox_id
        self.name = name
        self.external_id = external_id
        self.status = status
        self.allocated_to_track = allocated_to_track
        self.allocated_at = allocated_at
        self.lab_duration_hours = lab_duration_hours
        self.deletion_requested_at = deletion_requested_at
        self.deletion_retry_count = deletion_retry_count
        self.last_synced = last_synced
        self.idempotency_key = idempotency_key
        self.track_name = track_name
        self.created_at = created_at
        self.updated_at = updated_at

    @property
    def expires_at(self) -> Optional[int]:
        """Calculate when the allocation expires."""
        if self.allocated_at and self.status == SandboxStatus.ALLOCATED:
            return self.allocated_at + (self.lab_duration_hours * 3600)
        return None

    def is_expired(self, current_time: int, grace_period_minutes: int = 30) -> bool:
        """Check if allocation has expired (including grace period)."""
        if self.allocated_at and self.status == SandboxStatus.ALLOCATED:
            expiry_threshold = self.allocated_at + (self.lab_duration_hours * 3600) + (grace_period_minutes * 60)
            return current_time > expiry_threshold
        return False

    def can_be_allocated(self) -> bool:
        """Check if sandbox can be allocated."""
        return self.status == SandboxStatus.AVAILABLE

    def is_owned_by(self, track_id: str) -> bool:
        """Check if sandbox is owned by given track."""
        return self.status == SandboxStatus.ALLOCATED and self.allocated_to_track == track_id

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "sandbox_id": self.sandbox_id,
            "name": self.name,
            "external_id": self.external_id,
            "status": self.status.value,
            "allocated_to_track": self.allocated_to_track,
            "allocated_at": self.allocated_at,
            "lab_duration_hours": self.lab_duration_hours,
            "deletion_requested_at": self.deletion_requested_at,
            "deletion_retry_count": self.deletion_retry_count,
            "last_synced": self.last_synced,
            "idempotency_key": self.idempotency_key,
            "track_name": self.track_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
        }
