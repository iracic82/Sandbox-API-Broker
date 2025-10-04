"""Unit tests for Sandbox domain model."""

import pytest
from app.models.sandbox import Sandbox, SandboxStatus


def test_sandbox_creation():
    """Test basic sandbox creation."""
    sandbox = Sandbox(
        sandbox_id="test-123",
        name="test-sandbox",
        external_id="ext-456",
        status=SandboxStatus.AVAILABLE,
    )

    assert sandbox.sandbox_id == "test-123"
    assert sandbox.name == "test-sandbox"
    assert sandbox.status == SandboxStatus.AVAILABLE
    assert sandbox.can_be_allocated() is True


def test_sandbox_allocation():
    """Test sandbox allocation status."""
    sandbox = Sandbox(
        sandbox_id="test-123",
        name="test-sandbox",
        external_id="ext-456",
        status=SandboxStatus.ALLOCATED,
        allocated_to_track="track-abc",
        allocated_at=1000000,
        lab_duration_hours=4,
    )

    assert sandbox.can_be_allocated() is False
    assert sandbox.is_owned_by("track-abc") is True
    assert sandbox.is_owned_by("track-xyz") is False
    assert sandbox.expires_at == 1000000 + (4 * 3600)


def test_sandbox_expiry():
    """Test sandbox expiry logic."""
    sandbox = Sandbox(
        sandbox_id="test-123",
        name="test-sandbox",
        external_id="ext-456",
        status=SandboxStatus.ALLOCATED,
        allocated_to_track="track-abc",
        allocated_at=1000000,
        lab_duration_hours=4,
    )

    # Not expired within 4h
    current_time = 1000000 + (3 * 3600)
    assert sandbox.is_expired(current_time) is False

    # Expired after 4h + grace period
    current_time = 1000000 + (4 * 3600) + (31 * 60)  # 4h + 31min
    assert sandbox.is_expired(current_time, grace_period_minutes=30) is True


def test_sandbox_status_transitions():
    """Test valid status transitions."""
    # Available -> Allocated
    sandbox = Sandbox(
        sandbox_id="test-123",
        name="test-sandbox",
        external_id="ext-456",
        status=SandboxStatus.AVAILABLE,
    )
    assert sandbox.can_be_allocated() is True

    # Allocated -> Pending Deletion
    sandbox.status = SandboxStatus.ALLOCATED
    sandbox.allocated_to_track = "track-123"
    assert sandbox.can_be_allocated() is False
    assert sandbox.is_owned_by("track-123") is True

    # Pending Deletion -> Cannot allocate
    sandbox.status = SandboxStatus.PENDING_DELETION
    assert sandbox.can_be_allocated() is False
    assert sandbox.is_owned_by("track-123") is False  # No longer considered owner

    # Stale -> Cannot allocate
    sandbox.status = SandboxStatus.STALE
    assert sandbox.can_be_allocated() is False


def test_sandbox_to_dict():
    """Test sandbox serialization."""
    sandbox = Sandbox(
        sandbox_id="test-123",
        name="test-sandbox",
        external_id="ext-456",
        status=SandboxStatus.ALLOCATED,
        allocated_to_track="track-abc",
        allocated_at=1000000,
        lab_duration_hours=4,
    )

    data = sandbox.to_dict()

    assert data["sandbox_id"] == "test-123"
    assert data["status"] == "allocated"
    assert data["allocated_to_track"] == "track-abc"
    assert data["expires_at"] == 1000000 + (4 * 3600)
