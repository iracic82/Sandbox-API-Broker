"""Prometheus metrics for monitoring."""

import time
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from prometheus_client import CollectorRegistry
from typing import Optional

# Create a custom registry to avoid conflicts
registry = CollectorRegistry()

# Cache for pool gauges to avoid scanning DynamoDB on every /metrics request
_pool_gauges_cache = {
    "last_update": 0,
    "cache_ttl_seconds": 60,  # Cache for 60 seconds
}

# ============================================================================
# Counters - Monotonically increasing values
# ============================================================================

# Allocation metrics
allocate_total = Counter(
    "broker_allocate_total",
    "Total number of sandbox allocation requests",
    ["outcome"],  # success, no_sandboxes, error
    registry=registry,
)

allocate_idempotent_hits = Counter(
    "broker_allocate_idempotent_hits_total",
    "Total number of idempotent allocation requests (returned existing)",
    registry=registry,
)

allocate_conflicts = Counter(
    "broker_allocate_conflicts_total",
    "Total number of allocation conflicts (conditional write failed)",
    registry=registry,
)

# Deletion metrics
deletion_marked_total = Counter(
    "broker_deletion_marked_total",
    "Total number of sandboxes marked for deletion",
    ["outcome"],  # success, not_owner, expired, error
    registry=registry,
)

# Sync job metrics
sync_total = Counter(
    "broker_sync_total",
    "Total number of ENG CSP sync runs",
    ["outcome"],  # success, error
    registry=registry,
)

sync_sandboxes_synced = Counter(
    "broker_sync_sandboxes_synced_total",
    "Total number of sandboxes synced from ENG CSP",
    registry=registry,
)

sync_sandboxes_stale = Counter(
    "broker_sync_sandboxes_stale_total",
    "Total number of sandboxes marked as stale",
    registry=registry,
)

# Cleanup job metrics
cleanup_total = Counter(
    "broker_cleanup_total",
    "Total number of cleanup job runs",
    ["outcome"],  # success, error
    registry=registry,
)

cleanup_deleted = Counter(
    "broker_cleanup_deleted_total",
    "Total number of sandboxes successfully deleted",
    registry=registry,
)

cleanup_failed = Counter(
    "broker_cleanup_failed_total",
    "Total number of sandbox deletions that failed",
    registry=registry,
)

# Auto-expiry metrics
expiry_total = Counter(
    "broker_expiry_total",
    "Total number of auto-expiry job runs",
    ["outcome"],  # success, error
    registry=registry,
)

expiry_orphaned = Counter(
    "broker_expiry_orphaned_total",
    "Total number of orphaned allocations auto-expired",
    registry=registry,
)

# ============================================================================
# Gauges - Current state values (can go up or down)
# ============================================================================

pool_available = Gauge(
    "broker_pool_available",
    "Number of sandboxes currently available for allocation",
    registry=registry,
)

pool_allocated = Gauge(
    "broker_pool_allocated",
    "Number of sandboxes currently allocated to tracks",
    registry=registry,
)

pool_pending_deletion = Gauge(
    "broker_pool_pending_deletion",
    "Number of sandboxes pending deletion",
    registry=registry,
)

pool_stale = Gauge(
    "broker_pool_stale",
    "Number of stale sandboxes (no longer in ENG CSP)",
    registry=registry,
)

pool_deletion_failed = Gauge(
    "broker_pool_deletion_failed",
    "Number of sandboxes where deletion failed",
    registry=registry,
)

pool_total = Gauge(
    "broker_pool_total",
    "Total number of sandboxes in the pool",
    registry=registry,
)

# ============================================================================
# Histograms - Distribution of values
# ============================================================================

request_latency = Histogram(
    "broker_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint", "status"],
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0],
    registry=registry,
)

allocation_latency = Histogram(
    "broker_allocation_latency_seconds",
    "Sandbox allocation latency in seconds",
    ["outcome"],
    buckets=[0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0],
    registry=registry,
)

sync_duration = Histogram(
    "broker_sync_duration_seconds",
    "ENG CSP sync job duration in seconds",
    buckets=[1.0, 2.5, 5.0, 10.0, 15.0, 30.0, 60.0],
    registry=registry,
)

cleanup_duration = Histogram(
    "broker_cleanup_duration_seconds",
    "Cleanup job duration in seconds",
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
    registry=registry,
)


# ============================================================================
# Helper Functions
# ============================================================================

async def update_pool_gauges(db_client, force: bool = False):
    """
    Update all pool gauge metrics from DynamoDB with caching.

    Args:
        db_client: DynamoDB client
        force: If True, bypass cache and force update

    Should be called periodically (e.g., every 30s) or after pool changes.
    Cache prevents expensive DB scans on every /metrics request.
    """
    from app.models.sandbox import SandboxStatus

    # Check cache - only update if TTL expired or forced
    current_time = time.time()
    if not force and (current_time - _pool_gauges_cache["last_update"]) < _pool_gauges_cache["cache_ttl_seconds"]:
        # Cache is still valid, skip update
        return

    stats = {
        "total": 0,
        "available": 0,
        "allocated": 0,
        "pending_deletion": 0,
        "stale": 0,
        "deletion_failed": 0,
    }

    # Scan all sandboxes (cached for 60s to avoid overwhelming Prometheus scrapes)
    response = db_client.table.scan()

    for item in response.get("Items", []):
        stats["total"] += 1
        status = item.get("status")
        if status in stats:
            stats[status] += 1

    # Update gauges
    pool_total.set(stats["total"])
    pool_available.set(stats["available"])
    pool_allocated.set(stats["allocated"])
    pool_pending_deletion.set(stats["pending_deletion"])
    pool_stale.set(stats["stale"])
    pool_deletion_failed.set(stats["deletion_failed"])

    # Update cache timestamp
    _pool_gauges_cache["last_update"] = current_time


def get_metrics() -> tuple[bytes, str]:
    """
    Generate Prometheus metrics output.

    Returns:
        Tuple of (metrics_bytes, content_type)
    """
    return generate_latest(registry), CONTENT_TYPE_LATEST
