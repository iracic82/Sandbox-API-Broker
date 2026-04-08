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
    DELETED = "deleted"  # Soft-deleted, keeps history for analytics


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
        # NIOSXaaS cleanup tracking
        niosxaas_cleaned_at: Optional[int] = None,
        niosxaas_cleanup_skipped: bool = False,
        niosxaas_cleanup_failed_reason: Optional[str] = None,
        # Soft-delete tracking
        deleted_at: Optional[int] = None,
        # SFDC integration
        sfdc_account_id: Optional[str] = None,
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
        # NIOSXaaS cleanup tracking
        self.niosxaas_cleaned_at = niosxaas_cleaned_at
        self.niosxaas_cleanup_skipped = niosxaas_cleanup_skipped
        self.niosxaas_cleanup_failed_reason = niosxaas_cleanup_failed_reason
        # Soft-delete tracking
        self.deleted_at = deleted_at
        # SFDC integration
        self.sfdc_account_id = sfdc_account_id

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
            # NIOSXaaS cleanup tracking
            "niosxaas_cleaned_at": self.niosxaas_cleaned_at,
            "niosxaas_cleanup_skipped": self.niosxaas_cleanup_skipped,
            "niosxaas_cleanup_failed_reason": self.niosxaas_cleanup_failed_reason,
            # Soft-delete tracking
            "deleted_at": self.deleted_at,
            # SFDC integration
            "sfdc_account_id": self.sfdc_account_id,
        }
