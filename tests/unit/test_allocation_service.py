"""Unit tests for allocation service logic."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import time
from app.services.allocation import AllocationService
from app.models.sandbox import Sandbox, SandboxStatus
from app.db.dynamodb import DynamoDBClient


@pytest.fixture
def mock_db_client():
    """Mock DynamoDB client."""
    client = AsyncMock(spec=DynamoDBClient)
    return client


@pytest.fixture
def allocation_service(mock_db_client):
    """Allocation service with mocked DB client."""
    service = AllocationService()
    service.db = mock_db_client
    return service


@pytest.mark.asyncio
async def test_allocate_success_first_try(allocation_service, mock_db_client):
    """Test successful allocation on first candidate."""
    # Mock available candidates
    candidates = [
        Sandbox(
            sandbox_id='sb-1',
            name='sandbox-1',
            external_id='ext-1',
            status=SandboxStatus.AVAILABLE,
        )
    ]
    mock_db_client.get_available_candidates.return_value = candidates

    # Mock successful atomic allocation
    allocated_sandbox = Sandbox(
        sandbox_id='sb-1',
        name='sandbox-1',
        external_id='ext-1',
        status=SandboxStatus.ALLOCATED,
        allocated_to_track='track-123',
        allocated_at=int(time.time()),
    )
    mock_db_client.atomic_allocate.return_value = allocated_sandbox

    # No existing allocation by idempotency key
    mock_db_client.find_allocation_by_idempotency_key.return_value = None

    result = await allocation_service.allocate_sandbox(track_id='track-123')

    assert result is not None
    assert result.sandbox_id == 'sb-1'
    assert result.status == SandboxStatus.ALLOCATED
    mock_db_client.atomic_allocate.assert_called_once()


@pytest.mark.asyncio
async def test_allocate_retry_on_conflict(allocation_service, mock_db_client):
    """Test allocation retries on conflict."""
    # Mock available candidates
    candidates = [
        Sandbox(sandbox_id='sb-1', name='sandbox-1', external_id='ext-1', status=SandboxStatus.AVAILABLE),
        Sandbox(sandbox_id='sb-2', name='sandbox-2', external_id='ext-2', status=SandboxStatus.AVAILABLE),
    ]
    mock_db_client.get_available_candidates.return_value = candidates
    mock_db_client.find_allocation_by_idempotency_key.return_value = None

    # First attempt fails (conflict), second succeeds
    allocated_sandbox = Sandbox(
        sandbox_id='sb-2',
        name='sandbox-2',
        external_id='ext-2',
        status=SandboxStatus.ALLOCATED,
        allocated_to_track='track-123',
        allocated_at=int(time.time()),
    )
    mock_db_client.atomic_allocate.side_effect = [None, allocated_sandbox]

    result = await allocation_service.allocate_sandbox(track_id='track-123')

    assert result is not None
    assert result.sandbox_id == 'sb-2'
    assert mock_db_client.atomic_allocate.call_count == 2


@pytest.mark.asyncio
async def test_allocate_pool_exhausted(allocation_service, mock_db_client):
    """Test allocation fails when pool exhausted."""
    # No available candidates
    mock_db_client.get_available_candidates.return_value = []
    mock_db_client.find_allocation_by_idempotency_key.return_value = None

    from app.services.allocation import NoSandboxesAvailableError

    with pytest.raises(NoSandboxesAvailableError):
        await allocation_service.allocate_sandbox(track_id='track-123')


@pytest.mark.asyncio
async def test_allocate_all_conflicts(allocation_service, mock_db_client):
    """Test allocation fails when all candidates conflict."""
    # Mock available candidates
    candidates = [
        Sandbox(sandbox_id=f'sb-{i}', name=f'sandbox-{i}', external_id=f'ext-{i}', status=SandboxStatus.AVAILABLE)
        for i in range(15)  # K candidates
    ]
    mock_db_client.get_available_candidates.return_value = candidates
    mock_db_client.find_allocation_by_idempotency_key.return_value = None

    # All allocation attempts fail
    mock_db_client.atomic_allocate.return_value = None

    from app.services.allocation import NoSandboxesAvailableError

    with pytest.raises(NoSandboxesAvailableError):
        await allocation_service.allocate_sandbox(track_id='track-123')

    # Should have tried all K candidates
    assert mock_db_client.atomic_allocate.call_count == 15


@pytest.mark.asyncio
async def test_allocate_idempotency_returns_existing(allocation_service, mock_db_client):
    """Test idempotency returns existing allocation."""
    # Mock existing allocation by idempotency key
    existing_allocation = Sandbox(
        sandbox_id='sb-existing',
        name='sandbox-existing',
        external_id='ext-existing',
        status=SandboxStatus.ALLOCATED,
        allocated_to_track='track-123',
        allocated_at=int(time.time()) - 3600,
        idempotency_key='track-123',
    )
    mock_db_client.find_allocation_by_idempotency_key.return_value = existing_allocation

    result = await allocation_service.allocate_sandbox(track_id='track-123')

    assert result is not None
    assert result.sandbox_id == 'sb-existing'
    # Should not try to allocate new sandbox
    mock_db_client.get_available_candidates.assert_not_called()
    mock_db_client.atomic_allocate.assert_not_called()


@pytest.mark.asyncio
async def test_allocate_k_candidates_shuffled(allocation_service, mock_db_client):
    """Test that K candidates are fetched and shuffled (anti-thundering herd)."""
    # Mock available candidates
    candidates = [
        Sandbox(sandbox_id=f'sb-{i}', name=f'sandbox-{i}', external_id=f'ext-{i}', status=SandboxStatus.AVAILABLE)
        for i in range(15)
    ]
    mock_db_client.get_available_candidates.return_value = candidates
    mock_db_client.find_allocation_by_idempotency_key.return_value = None

    # First candidate succeeds
    allocated_sandbox = Sandbox(
        sandbox_id='sb-0',
        name='sandbox-0',
        external_id='ext-0',
        status=SandboxStatus.ALLOCATED,
        allocated_to_track='track-123',
        allocated_at=int(time.time()),
    )
    mock_db_client.atomic_allocate.return_value = allocated_sandbox

    result = await allocation_service.allocate_sandbox(track_id='track-123')

    # Verify K candidates were fetched (default K=15)
    mock_db_client.get_available_candidates.assert_called_once()
    call_kwargs = mock_db_client.get_available_candidates.call_args[1]
    assert call_kwargs.get('k', 15) == 15


@pytest.mark.asyncio
async def test_mark_for_deletion_success(allocation_service, mock_db_client):
    """Test successful mark for deletion."""
    marked_sandbox = Sandbox(
        sandbox_id='sb-1',
        name='sandbox-1',
        external_id='ext-1',
        status=SandboxStatus.PENDING_DELETION,
        allocated_to_track='track-123',
        deletion_requested_at=int(time.time()),
    )
    mock_db_client.mark_for_deletion.return_value = marked_sandbox

    result = await allocation_service.mark_for_deletion(
        sandbox_id='sb-1',
        track_id='track-123'
    )

    assert result is not None
    assert result.status == SandboxStatus.PENDING_DELETION
    mock_db_client.mark_for_deletion.assert_called_once()


@pytest.mark.asyncio
async def test_mark_for_deletion_not_owner(allocation_service, mock_db_client):
    """Test mark for deletion fails when not owner."""
    # Mock existing sandbox (owned by different track)
    existing_sandbox = Sandbox(
        sandbox_id='sb-1',
        name='sandbox-1',
        external_id='ext-1',
        status=SandboxStatus.ALLOCATED,
        allocated_to_track='other-track',  # Different owner
    )
    mock_db_client.get_sandbox.return_value = existing_sandbox
    mock_db_client.mark_for_deletion.return_value = None

    from app.services.allocation import NotSandboxOwnerError

    with pytest.raises(NotSandboxOwnerError):
        await allocation_service.mark_for_deletion(
            sandbox_id='sb-1',
            track_id='wrong-track'
        )


@pytest.mark.asyncio
async def test_mark_for_deletion_validates_expiry(allocation_service, mock_db_client):
    """Test mark for deletion validates expiry time."""
    current_time = int(time.time())
    max_expiry_time = current_time - (4 * 3600) - (30 * 60)  # 4h + 30min grace

    await allocation_service.mark_for_deletion(
        sandbox_id='sb-1',
        track_id='track-123'
    )

    # Verify max_expiry_time is calculated correctly
    call_kwargs = mock_db_client.mark_for_deletion.call_args[1]
    assert 'max_expiry_time' in call_kwargs
    # Should prevent deletion of expired sandboxes
    assert call_kwargs['max_expiry_time'] < current_time


@pytest.mark.asyncio
async def test_get_sandbox(allocation_service, mock_db_client):
    """Test get sandbox by ID."""
    sandbox = Sandbox(
        sandbox_id='sb-1',
        name='sandbox-1',
        external_id='ext-1',
        status=SandboxStatus.ALLOCATED,
        allocated_to_track='track-123',
    )
    mock_db_client.get_sandbox.return_value = sandbox

    result = await allocation_service.get_sandbox('sb-1', 'track-123')

    assert result is not None
    assert result.sandbox_id == 'sb-1'
    mock_db_client.get_sandbox.assert_called_once_with('sb-1')


@pytest.mark.asyncio
async def test_allocation_with_custom_lab_duration(allocation_service, mock_db_client):
    """Test allocation respects custom lab duration."""
    candidates = [
        Sandbox(
            sandbox_id='sb-1',
            name='sandbox-1',
            external_id='ext-1',
            status=SandboxStatus.AVAILABLE,
            lab_duration_hours=6,  # Custom duration
        )
    ]
    mock_db_client.get_available_candidates.return_value = candidates
    mock_db_client.find_allocation_by_idempotency_key.return_value = None

    allocated_sandbox = Sandbox(
        sandbox_id='sb-1',
        name='sandbox-1',
        external_id='ext-1',
        status=SandboxStatus.ALLOCATED,
        allocated_to_track='track-123',
        allocated_at=int(time.time()),
        lab_duration_hours=6,
    )
    mock_db_client.atomic_allocate.return_value = allocated_sandbox

    result = await allocation_service.allocate_sandbox(track_id='track-123')

    assert result.lab_duration_hours == 6
    # Expiry should be 6 hours
    assert result.expires_at == result.allocated_at + (6 * 3600)
