"""Unit tests for DynamoDB client."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from botocore.exceptions import ClientError
from app.db.dynamodb import DynamoDBClient
from app.models.sandbox import Sandbox, SandboxStatus


@pytest.fixture
def mock_dynamodb_table():
    """Mock DynamoDB table."""
    table = Mock()
    table.get_item = Mock()
    table.put_item = Mock()
    table.update_item = Mock()
    table.query = Mock()
    return table


@pytest.fixture
def db_client(mock_dynamodb_table):
    """DynamoDB client with mocked table."""
    with patch('app.db.dynamodb.boto3.resource') as mock_resource:
        mock_dynamodb = Mock()
        mock_dynamodb.Table.return_value = mock_dynamodb_table
        mock_resource.return_value = mock_dynamodb

        client = DynamoDBClient()
        client.table = mock_dynamodb_table
        return client


@pytest.mark.asyncio
async def test_get_sandbox_success(db_client, mock_dynamodb_table):
    """Test successful sandbox retrieval."""
    mock_dynamodb_table.get_item.return_value = {
        'Item': {
            'PK': 'SBX#test-123',
            'SK': 'META',
            'sandbox_id': 'test-123',
            'name': 'test-sandbox',
            'external_id': 'ext-456',
            'status': 'available',
            'lab_duration_hours': 4,
            'deletion_retry_count': 0,
            'allocated_at': 0,
        }
    }

    sandbox = await db_client.get_sandbox('test-123')

    assert sandbox is not None
    assert sandbox.sandbox_id == 'test-123'
    assert sandbox.status == SandboxStatus.AVAILABLE
    mock_dynamodb_table.get_item.assert_called_once_with(
        Key={'PK': 'SBX#test-123', 'SK': 'META'}
    )


@pytest.mark.asyncio
async def test_get_sandbox_not_found(db_client, mock_dynamodb_table):
    """Test sandbox not found returns None."""
    mock_dynamodb_table.get_item.return_value = {}

    sandbox = await db_client.get_sandbox('nonexistent')

    assert sandbox is None


@pytest.mark.asyncio
async def test_get_sandbox_error(db_client, mock_dynamodb_table):
    """Test error handling in get_sandbox."""
    mock_dynamodb_table.get_item.side_effect = ClientError(
        {'Error': {'Code': 'InternalServerError', 'Message': 'Server error'}},
        'GetItem'
    )

    with pytest.raises(Exception, match="DynamoDB error getting sandbox"):
        await db_client.get_sandbox('test-123')


@pytest.mark.asyncio
async def test_atomic_allocate_success(db_client, mock_dynamodb_table):
    """Test successful atomic allocation."""
    mock_dynamodb_table.update_item.return_value = {
        'Attributes': {
            'PK': 'SBX#test-123',
            'SK': 'META',
            'sandbox_id': 'test-123',
            'name': 'test-sandbox',
            'external_id': 'ext-456',
            'status': 'allocated',
            'allocated_to_track': 'track-abc',
            'allocated_at': 1000000,
            'idempotency_key': 'idem-key-123',
            'lab_duration_hours': 4,
            'deletion_retry_count': 0,
        }
    }

    sandbox = await db_client.atomic_allocate(
        sandbox_id='test-123',
        track_id='track-abc',
        idempotency_key='idem-key-123',
        current_time=1000000
    )

    assert sandbox is not None
    assert sandbox.sandbox_id == 'test-123'
    assert sandbox.status == SandboxStatus.ALLOCATED
    assert sandbox.allocated_to_track == 'track-abc'
    assert sandbox.idempotency_key == 'idem-key-123'


@pytest.mark.asyncio
async def test_atomic_allocate_already_allocated(db_client, mock_dynamodb_table):
    """Test allocation fails when sandbox already allocated."""
    mock_dynamodb_table.update_item.side_effect = ClientError(
        {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Condition failed'}},
        'UpdateItem'
    )

    sandbox = await db_client.atomic_allocate(
        sandbox_id='test-123',
        track_id='track-abc',
        idempotency_key='idem-key-123',
        current_time=1000000
    )

    assert sandbox is None


@pytest.mark.asyncio
async def test_get_available_candidates(db_client, mock_dynamodb_table):
    """Test fetching available sandbox candidates."""
    mock_dynamodb_table.query.return_value = {
        'Items': [
            {
                'sandbox_id': 'sb-1',
                'name': 'sandbox-1',
                'external_id': 'ext-1',
                'status': 'available',
                'lab_duration_hours': 4,
                'deletion_retry_count': 0,
                'allocated_at': 0,
            },
            {
                'sandbox_id': 'sb-2',
                'name': 'sandbox-2',
                'external_id': 'ext-2',
                'status': 'available',
                'lab_duration_hours': 4,
                'deletion_retry_count': 0,
                'allocated_at': 0,
            },
        ]
    }

    sandboxes = await db_client.get_available_candidates(k=15)

    assert len(sandboxes) == 2
    assert all(sb.status == SandboxStatus.AVAILABLE for sb in sandboxes)

    # Verify query was called with correct parameters
    call_kwargs = mock_dynamodb_table.query.call_args[1]
    assert call_kwargs['Limit'] == 15
    assert 'KeyConditionExpression' in call_kwargs


@pytest.mark.asyncio
async def test_mark_for_deletion_success(db_client, mock_dynamodb_table):
    """Test successful mark for deletion."""
    mock_dynamodb_table.update_item.return_value = {
        'Attributes': {
            'PK': 'SBX#test-123',
            'SK': 'META',
            'sandbox_id': 'test-123',
            'name': 'test-sandbox',
            'external_id': 'ext-456',
            'status': 'pending_deletion',
            'allocated_to_track': 'track-abc',
            'allocated_at': 1000000,
            'deletion_requested_at': 1010000,
            'lab_duration_hours': 4,
            'deletion_retry_count': 0,
        }
    }

    sandbox = await db_client.mark_for_deletion(
        sandbox_id='test-123',
        track_id='track-abc',
        current_time=1010000,
        max_expiry_time=900000
    )

    assert sandbox is not None
    assert sandbox.status == SandboxStatus.PENDING_DELETION
    assert sandbox.deletion_requested_at == 1010000


@pytest.mark.asyncio
async def test_mark_for_deletion_not_owner(db_client, mock_dynamodb_table):
    """Test mark for deletion fails when not owner."""
    mock_dynamodb_table.update_item.side_effect = ClientError(
        {'Error': {'Code': 'ConditionalCheckFailedException', 'Message': 'Condition failed'}},
        'UpdateItem'
    )

    sandbox = await db_client.mark_for_deletion(
        sandbox_id='test-123',
        track_id='wrong-track',
        current_time=1010000,
        max_expiry_time=900000
    )

    assert sandbox is None


@pytest.mark.asyncio
async def test_put_sandbox(db_client, mock_dynamodb_table):
    """Test putting/upserting sandbox."""
    sandbox = Sandbox(
        sandbox_id='test-123',
        name='test-sandbox',
        external_id='ext-456',
        status=SandboxStatus.AVAILABLE,
    )

    result = await db_client.put_sandbox(sandbox)

    assert result.sandbox_id == 'test-123'
    assert result.updated_at is not None
    assert result.created_at is not None
    mock_dynamodb_table.put_item.assert_called_once()


@pytest.mark.asyncio
async def test_find_allocation_by_idempotency_key(db_client, mock_dynamodb_table):
    """Test finding allocation by idempotency key."""
    mock_dynamodb_table.query.return_value = {
        'Items': [
            {
                'sandbox_id': 'test-123',
                'name': 'test-sandbox',
                'external_id': 'ext-456',
                'status': 'allocated',
                'allocated_to_track': 'track-abc',
                'allocated_at': 1000000,
                'idempotency_key': 'idem-key-123',
                'lab_duration_hours': 4,
                'deletion_retry_count': 0,
            }
        ]
    }

    sandbox = await db_client.find_allocation_by_idempotency_key('idem-key-123')

    assert sandbox is not None
    assert sandbox.sandbox_id == 'test-123'
    assert sandbox.idempotency_key == 'idem-key-123'


@pytest.mark.asyncio
async def test_find_allocation_by_idempotency_key_not_found(db_client, mock_dynamodb_table):
    """Test idempotency key not found."""
    mock_dynamodb_table.query.return_value = {'Items': []}

    sandbox = await db_client.find_allocation_by_idempotency_key('nonexistent')

    assert sandbox is None


@pytest.mark.asyncio
async def test_find_allocation_by_idempotency_key_not_allocated(db_client, mock_dynamodb_table):
    """Test idempotency key found but sandbox not allocated."""
    mock_dynamodb_table.query.return_value = {
        'Items': [
            {
                'sandbox_id': 'test-123',
                'name': 'test-sandbox',
                'external_id': 'ext-456',
                'status': 'pending_deletion',  # Not allocated anymore
                'idempotency_key': 'idem-key-123',
                'lab_duration_hours': 4,
                'deletion_retry_count': 0,
                'allocated_at': 0,
            }
        ]
    }

    sandbox = await db_client.find_allocation_by_idempotency_key('idem-key-123')

    assert sandbox is None  # Should return None because not allocated


@pytest.mark.asyncio
async def test_to_item_conversion(db_client):
    """Test sandbox to DynamoDB item conversion."""
    sandbox = Sandbox(
        sandbox_id='test-123',
        name='test-sandbox',
        external_id='ext-456',
        status=SandboxStatus.ALLOCATED,
        allocated_to_track='track-abc',
        allocated_at=1000000,
        idempotency_key='idem-key-123',
        lab_duration_hours=4,
    )

    item = db_client._to_item(sandbox)

    assert item['PK'] == 'SBX#test-123'
    assert item['SK'] == 'META'
    assert item['sandbox_id'] == 'test-123'
    assert item['status'] == 'allocated'
    assert item['allocated_to_track'] == 'track-abc'
    assert item['idempotency_key'] == 'idem-key-123'


@pytest.mark.asyncio
async def test_from_item_conversion(db_client):
    """Test DynamoDB item to sandbox conversion."""
    item = {
        'PK': 'SBX#test-123',
        'SK': 'META',
        'sandbox_id': 'test-123',
        'name': 'test-sandbox',
        'external_id': 'ext-456',
        'status': 'allocated',
        'allocated_to_track': 'track-abc',
        'allocated_at': 1000000,
        'idempotency_key': 'idem-key-123',
        'lab_duration_hours': 4,
        'deletion_retry_count': 0,
    }

    sandbox = db_client._from_item(item)

    assert sandbox.sandbox_id == 'test-123'
    assert sandbox.status == SandboxStatus.ALLOCATED
    assert sandbox.allocated_to_track == 'track-abc'
    assert sandbox.idempotency_key == 'idem-key-123'
