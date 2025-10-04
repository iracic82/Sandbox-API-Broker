# DynamoDB Schema - Sandbox Broker API

## Table: `SandboxPool`

### Primary Key
- **PK** (Partition Key): `SBX#{sandbox_id}` - String
- **SK** (Sort Key): `META` - String (always "META" for sandbox items)

### Attributes

#### Core Attributes (Always Present)
| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `PK` | String | Partition key | `SBX#abc123` |
| `SK` | String | Sort key | `META` |
| `sandbox_id` | String | Unique sandbox identifier (UUID) | `abc123` |
| `name` | String | Human-readable name | `test-sandbox-1` |
| `external_id` | String | ENG CSP identifier | `ext-xyz-456` |
| `status` | String | Current state (enum) | `available`, `allocated`, `pending_deletion`, `stale` |
| `lab_duration_hours` | Number | Max lab duration | `4` |
| `deletion_retry_count` | Number | Failed deletion attempts | `0` |
| `allocated_at` | Number | Unix timestamp (0 for available) | `1759567084` or `0` |
| `created_at` | Number | Unix timestamp when created | `1759567084` |
| `updated_at` | Number | Unix timestamp when updated | `1759567084` |

#### Conditional Attributes (Present Based on State)
| Attribute | Type | When Present | Description |
|-----------|------|--------------|-------------|
| `allocated_to_track` | String | When allocated | Track ID that owns sandbox |
| `idempotency_key` | String | When allocated | Deduplication key (X-Track-ID) |
| `deletion_requested_at` | Number | When pending_deletion | Unix timestamp of deletion request |
| `last_synced` | Number | After sync | Unix timestamp of last ENG sync |

## Global Secondary Indexes (GSI)

### GSI1: StatusIndex
**Purpose**: Query sandboxes by status (find available sandboxes)

- **PK**: `status` (String) - e.g., "available", "allocated"
- **SK**: `allocated_at` (Number) - Sort by allocation time
- **Projection**: ALL (all attributes)

**Usage**:
```python
# Find available sandboxes
response = table.query(
    IndexName="StatusIndex",
    KeyConditionExpression="#status = :status",
    ExpressionAttributeNames={"#status": "status"},
    ExpressionAttributeValues={":status": "available"},
    Limit=15
)
```

### GSI2: TrackIndex
**Purpose**: Query sandboxes by track (find what a track owns)

- **PK**: `allocated_to_track` (String) - e.g., "track-123"
- **SK**: `allocated_at` (Number) - Sort by allocation time
- **Projection**: ALL

**Usage**:
```python
# Find all sandboxes owned by a track
response = table.query(
    IndexName="TrackIndex",
    KeyConditionExpression="allocated_to_track = :track",
    ExpressionAttributeValues={":track": "track-123"}
)
```

### GSI3: IdempotencyIndex
**Purpose**: Idempotency lookups (find existing allocation by idempotency key)

- **PK**: `idempotency_key` (String) - e.g., "track-123"
- **SK**: `allocated_at` (Number) - Sort by allocation time
- **Projection**: ALL

**Usage**:
```python
# Check for existing allocation (idempotency)
response = table.query(
    IndexName="IdempotencyIndex",
    KeyConditionExpression="idempotency_key = :key",
    ExpressionAttributeValues={":key": "track-123"},
    Limit=1
)
```

## Sandbox Lifecycle States

### 1. AVAILABLE (Initial State)
```json
{
  "PK": "SBX#abc123",
  "SK": "META",
  "sandbox_id": "abc123",
  "name": "test-sandbox-1",
  "external_id": "ext-xyz-456",
  "status": "available",
  "lab_duration_hours": 4,
  "deletion_retry_count": 0,
  "allocated_at": 0,
  "created_at": 1759567084,
  "updated_at": 1759567084,
  "last_synced": 1759567084
}
```

**Key Points**:
- `allocated_at = 0` (required for GSI1 sort key)
- No `allocated_to_track` or `idempotency_key`
- Can be queried via GSI1 (StatusIndex)

### 2. ALLOCATED (After POST /v1/allocate)
```json
{
  "PK": "SBX#abc123",
  "SK": "META",
  "sandbox_id": "abc123",
  "name": "test-sandbox-1",
  "external_id": "ext-xyz-456",
  "status": "allocated",
  "lab_duration_hours": 4,
  "deletion_retry_count": 0,
  "allocated_at": 1759567084,
  "allocated_to_track": "track-123",
  "idempotency_key": "track-123",
  "created_at": 1759567084,
  "updated_at": 1759567084
}
```

**Key Points**:
- `allocated_at` = current timestamp (for expiry calculation)
- `allocated_to_track` = owning track ID
- `idempotency_key` = X-Track-ID header value
- Can be queried via GSI2 (TrackIndex) or GSI3 (IdempotencyIndex)

### 3. PENDING_DELETION (After POST /mark-for-deletion)
```json
{
  "PK": "SBX#abc123",
  "SK": "META",
  "sandbox_id": "abc123",
  "name": "test-sandbox-1",
  "external_id": "ext-xyz-456",
  "status": "pending_deletion",
  "lab_duration_hours": 4,
  "deletion_retry_count": 0,
  "allocated_at": 1759567084,
  "allocated_to_track": "track-123",
  "idempotency_key": "track-123",
  "deletion_requested_at": 1759567090,
  "created_at": 1759567084,
  "updated_at": 1759567090
}
```

**Key Points**:
- `status = "pending_deletion"`
- `deletion_requested_at` = timestamp when marked
- Cleanup job will process and delete from ENG CSP
- Not allocatable (filtered out of GSI1 available queries)

### 4. STALE (Missing from ENG Sync)
```json
{
  "PK": "SBX#abc123",
  "SK": "META",
  "sandbox_id": "abc123",
  "name": "test-sandbox-1",
  "external_id": "ext-xyz-456",
  "status": "stale",
  "lab_duration_hours": 4,
  "deletion_retry_count": 0,
  "allocated_at": 0,
  "created_at": 1759567084,
  "updated_at": 1759567200,
  "last_synced": 1759567000
}
```

**Key Points**:
- `status = "stale"` (not found in ENG CSP sync)
- Not allocatable
- Requires manual investigation

## Atomic Operations

### Conditional Write (Allocation)
Ensures only available sandboxes can be allocated:

```python
table.update_item(
    Key={"PK": f"SBX#{sandbox_id}", "SK": "META"},
    UpdateExpression="""
        SET #status = :allocated,
            allocated_to_track = :track_id,
            allocated_at = :now,
            idempotency_key = :idem_key,
            updated_at = :now
    """,
    ConditionExpression="attribute_exists(PK) AND #status = :available",
    ExpressionAttributeNames={"#status": "status"},
    ExpressionAttributeValues={
        ":allocated": "allocated",
        ":available": "available",
        ":track_id": "track-123",
        ":now": 1759567084,
        ":idem_key": "track-123"
    }
)
```

**Atomicity Guarantee**: If two tracks try to allocate the same sandbox simultaneously, only one succeeds. The other gets `ConditionalCheckFailedException`.

### Conditional Write (Mark for Deletion)
Ensures only the owner can mark within 4-hour window:

```python
table.update_item(
    Key={"PK": f"SBX#{sandbox_id}", "SK": "META"},
    UpdateExpression="""
        SET #status = :pending_deletion,
            deletion_requested_at = :now,
            updated_at = :now
    """,
    ConditionExpression="""
        attribute_exists(PK) AND
        #status = :allocated AND
        allocated_to_track = :track_id AND
        allocated_at > :max_expiry
    """,
    ExpressionAttributeNames={"#status": "status"},
    ExpressionAttributeValues={
        ":pending_deletion": "pending_deletion",
        ":allocated": "allocated",
        ":track_id": "track-123",
        ":now": 1759567090,
        ":max_expiry": 1759552684  # now - 4 hours
    }
)
```

**Validation**: Fails if:
- Status is not "allocated"
- Different track tries to delete
- Allocation expired (older than 4 hours)

## Reserved Keywords Handling

DynamoDB has reserved keywords (e.g., "status"). Always use `ExpressionAttributeNames`:

```python
# ❌ WRONG - will fail
KeyConditionExpression="status = :status"

# ✅ CORRECT
KeyConditionExpression="#status = :status",
ExpressionAttributeNames={"#status": "status"}
```

## Capacity Planning

### On-Demand Mode (Recommended for Phase 1)
- Automatically scales with traffic
- No capacity planning required
- Pay per request

### Provisioned Mode (For production with predictable traffic)
- **Read Capacity**: ~20 RCU per GSI
- **Write Capacity**: ~10 WCU for table
- Enable auto-scaling (target 70% utilization)

## Access Patterns

| Pattern | Index Used | Query |
|---------|-----------|-------|
| Find available sandboxes | GSI1 (StatusIndex) | `status = "available"` |
| Check idempotency | GSI3 (IdempotencyIndex) | `idempotency_key = "track-123"` |
| Find track's sandboxes | GSI2 (TrackIndex) | `allocated_to_track = "track-123"` |
| Get specific sandbox | Main table | `PK = "SBX#abc123" AND SK = "META"` |
| Find expired allocations | Table scan (auto-expiry job) | `status = "allocated" AND allocated_at < cutoff` |
| Find pending deletions | Table scan (cleanup job) | `status = "pending_deletion"` |

## Notes

1. **`allocated_at` is always present**: Set to `0` for available sandboxes (GSI sort key requirement)
2. **Status is a reserved keyword**: Always use `#status` with ExpressionAttributeNames
3. **Timestamps are Unix epoch**: All times stored as integers (seconds since 1970-01-01)
4. **UUIDs for sandbox_id**: Ensures good partition key distribution
5. **Immutable external_id**: Maps to ENG CSP sandbox (never changes)
