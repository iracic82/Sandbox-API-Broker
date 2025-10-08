"""Unit tests for multi-student same-lab allocation scenario."""

import pytest
from unittest.mock import AsyncMock, patch
from app.services.allocation import AllocationService
from app.models.sandbox import Sandbox, SandboxStatus


@pytest.mark.asyncio
async def test_multiple_students_same_lab_different_sandboxes():
    """
    Test that multiple students taking the same lab get different sandboxes.

    Scenario:
    - Lab: "aws-security-101" (same for all students)
    - Student 1: instruqt_sandbox_id = "inst-student1-abc"
    - Student 2: instruqt_sandbox_id = "inst-student2-def"
    - Student 3: instruqt_sandbox_id = "inst-student3-ghi"

    Each student should get a DIFFERENT sandbox from the pool.
    """
    service = AllocationService()

    # Mock 3 available sandboxes
    sandbox1 = Sandbox(
        sandbox_id="sbx-001",
        name="sandbox-1",
        external_id="ext-001",
        status=SandboxStatus.AVAILABLE,
    )
    sandbox2 = Sandbox(
        sandbox_id="sbx-002",
        name="sandbox-2",
        external_id="ext-002",
        status=SandboxStatus.AVAILABLE,
    )
    sandbox3 = Sandbox(
        sandbox_id="sbx-003",
        name="sandbox-3",
        external_id="ext-003",
        status=SandboxStatus.AVAILABLE,
    )

    # Mock database methods
    with patch.object(service.db, 'find_allocation_by_idempotency_key', new=AsyncMock(return_value=None)):
        with patch.object(service.db, 'get_available_candidates', new=AsyncMock(return_value=[sandbox1, sandbox2, sandbox3])):
            # Mock atomic_allocate to succeed on first try for each student
            allocated_sandboxes = []

            async def mock_atomic_allocate(sandbox_id, track_id, idempotency_key, current_time, track_name=None):
                # Allocate the sandbox to this specific student
                if sandbox_id == "sbx-001" and "student1" in track_id:
                    allocated = Sandbox(
                        sandbox_id=sandbox1.sandbox_id,
                        name=sandbox1.name,
                        external_id=sandbox1.external_id,
                        status=SandboxStatus.ALLOCATED,
                        allocated_to_track=track_id,
                        idempotency_key=idempotency_key,
                        allocated_at=current_time,
                    )
                    allocated_sandboxes.append(allocated)
                    return allocated
                elif sandbox_id == "sbx-002" and "student2" in track_id:
                    allocated = Sandbox(
                        sandbox_id=sandbox2.sandbox_id,
                        name=sandbox2.name,
                        external_id=sandbox2.external_id,
                        status=SandboxStatus.ALLOCATED,
                        allocated_to_track=track_id,
                        idempotency_key=idempotency_key,
                        allocated_at=current_time,
                    )
                    allocated_sandboxes.append(allocated)
                    return allocated
                elif sandbox_id == "sbx-003" and "student3" in track_id:
                    allocated = Sandbox(
                        sandbox_id=sandbox3.sandbox_id,
                        name=sandbox3.name,
                        external_id=sandbox3.external_id,
                        status=SandboxStatus.ALLOCATED,
                        allocated_to_track=track_id,
                        idempotency_key=idempotency_key,
                        allocated_at=current_time,
                    )
                    allocated_sandboxes.append(allocated)
                    return allocated
                # Conflict - sandbox taken by another student
                return None

            with patch.object(service.db, 'atomic_allocate', new=AsyncMock(side_effect=mock_atomic_allocate)):
                # Student 1 allocates
                result1 = await service.allocate_sandbox(
                    track_id="inst-student1-abc",
                    instruqt_track_id="aws-security-101"
                )

                # Student 2 allocates
                result2 = await service.allocate_sandbox(
                    track_id="inst-student2-def",
                    instruqt_track_id="aws-security-101"
                )

                # Student 3 allocates
                result3 = await service.allocate_sandbox(
                    track_id="inst-student3-ghi",
                    instruqt_track_id="aws-security-101"
                )

    # Verify each student got a DIFFERENT sandbox
    assert result1.sandbox_id != result2.sandbox_id
    assert result2.sandbox_id != result3.sandbox_id
    assert result1.sandbox_id != result3.sandbox_id

    # Verify each student is tracked separately
    assert result1.allocated_to_track == "inst-student1-abc"
    assert result2.allocated_to_track == "inst-student2-def"
    assert result3.allocated_to_track == "inst-student3-ghi"

    # Verify all are for the same lab (if we added this tracking)
    # This would be used for analytics only
    assert len(allocated_sandboxes) == 3


@pytest.mark.asyncio
async def test_same_student_idempotency_returns_same_sandbox():
    """
    Test that the same student (same instruqt_sandbox_id) making multiple requests
    gets the SAME sandbox back (idempotency).
    """
    import time
    service = AllocationService()

    # Mock allocated sandbox (with current timestamp so it's not expired)
    current_time = int(time.time())
    allocated_sandbox = Sandbox(
        sandbox_id="sbx-001",
        name="sandbox-1",
        external_id="ext-001",
        status=SandboxStatus.ALLOCATED,
        allocated_to_track="inst-student1-abc",
        idempotency_key="inst-student1-abc",
        allocated_at=current_time,
    )

    # Mock always returns existing allocation (idempotency)
    with patch.object(service.db, 'find_allocation_by_idempotency_key', new=AsyncMock(return_value=allocated_sandbox)):
        result1 = await service.allocate_sandbox(
            track_id="inst-student1-abc",
            instruqt_track_id="aws-security-101"
        )

        result2 = await service.allocate_sandbox(
            track_id="inst-student1-abc",
            instruqt_track_id="aws-security-101"
        )

    # Same sandbox returned both times (idempotent)
    assert result1.sandbox_id == result2.sandbox_id == "sbx-001"
    assert result1.allocated_to_track == result2.allocated_to_track == "inst-student1-abc"


@pytest.mark.asyncio
async def test_legacy_header_backward_compatibility():
    """
    Test that old X-Track-ID header still works (backward compatibility).

    Old API usage:
    - X-Track-ID: unique-student-id

    Should still allocate correctly.
    """
    service = AllocationService()

    sandbox = Sandbox(
        sandbox_id="sbx-001",
        name="sandbox-1",
        external_id="ext-001",
        status=SandboxStatus.AVAILABLE,
    )

    with patch.object(service.db, 'find_allocation_by_idempotency_key', new=AsyncMock(return_value=None)):
        with patch.object(service.db, 'get_available_candidates', new=AsyncMock(return_value=[sandbox])):

            async def mock_allocate(sandbox_id, track_id, idempotency_key, current_time, track_name=None):
                allocated = Sandbox(
                    sandbox_id=sandbox.sandbox_id,
                    name=sandbox.name,
                    external_id=sandbox.external_id,
                    status=SandboxStatus.ALLOCATED,
                    allocated_to_track=track_id,
                    idempotency_key=idempotency_key,
                    allocated_at=current_time,
                )
                return allocated

            with patch.object(service.db, 'atomic_allocate', new=AsyncMock(side_effect=mock_allocate)):
                # Using legacy header format (just track_id, no instruqt_track_id)
                result = await service.allocate_sandbox(
                    track_id="legacy-track-id-123"
                )

    assert result.sandbox_id == "sbx-001"
    assert result.allocated_to_track == "legacy-track-id-123"
