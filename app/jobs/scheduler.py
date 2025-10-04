"""Background job scheduler using asyncio tasks."""

import asyncio
import time
from typing import Optional
from app.core.config import settings
from app.services.admin import admin_service
from app.db.dynamodb import db_client
from app.models.sandbox import SandboxStatus
from app.core.metrics import expiry_total, expiry_orphaned
from app.core.logging import log_request

# Global task references
_scheduler_tasks: list[asyncio.Task] = []
_shutdown_event: Optional[asyncio.Event] = None


async def sync_job():
    """
    ENG CSP sync job - runs every SYNC_INTERVAL_SEC.

    Fetches sandboxes from ENG tenant and syncs to DynamoDB.
    """
    job_name = "sync_job"
    print(f"[{job_name}] Starting (interval: {settings.sync_interval_sec}s)")

    while not _shutdown_event.is_set():
        try:
            print(f"[{job_name}] Running sync...")
            result = await admin_service.trigger_sync()
            log_request(
                request_id=f"job-sync-{int(time.time())}",
                action="background_sync",
                outcome="success",
                latency_ms=result["duration_ms"],
                message=f"Synced {result['synced']} sandboxes, marked {result['marked_stale']} as stale",
            )
        except Exception as e:
            log_request(
                request_id=f"job-sync-{int(time.time())}",
                action="background_sync",
                outcome="error",
                error=str(e),
                message=f"Sync job failed: {e}",
            )

        # Wait for next interval (or shutdown)
        try:
            await asyncio.wait_for(
                _shutdown_event.wait(),
                timeout=settings.sync_interval_sec
            )
            break  # Shutdown requested
        except asyncio.TimeoutError:
            continue  # Normal interval timeout, run again


async def cleanup_job():
    """
    Cleanup job - runs every CLEANUP_INTERVAL_SEC.

    Processes pending_deletion sandboxes and deletes from ENG CSP.
    """
    job_name = "cleanup_job"
    print(f"[{job_name}] Starting (interval: {settings.cleanup_interval_sec}s)")

    while not _shutdown_event.is_set():
        try:
            print(f"[{job_name}] Running cleanup...")
            result = await admin_service.trigger_cleanup()
            log_request(
                request_id=f"job-cleanup-{int(time.time())}",
                action="background_cleanup",
                outcome="success",
                latency_ms=result["duration_ms"],
                message=f"Deleted {result['deleted']} sandboxes, {result['failed']} failed",
            )
        except Exception as e:
            log_request(
                request_id=f"job-cleanup-{int(time.time())}",
                action="background_cleanup",
                outcome="error",
                error=str(e),
                message=f"Cleanup job failed: {e}",
            )

        # Wait for next interval (or shutdown)
        try:
            await asyncio.wait_for(
                _shutdown_event.wait(),
                timeout=settings.cleanup_interval_sec
            )
            break  # Shutdown requested
        except asyncio.TimeoutError:
            continue  # Normal interval timeout, run again


async def auto_expiry_job():
    """
    Auto-expiry job - runs every AUTO_EXPIRY_INTERVAL_SEC.

    Finds orphaned allocations (>4.5h old) and marks them for deletion.
    """
    job_name = "auto_expiry_job"
    grace_period_sec = settings.grace_period_minutes * 60
    expiry_threshold_sec = settings.lab_duration_seconds + grace_period_sec

    print(f"[{job_name}] Starting (interval: {settings.auto_expiry_interval_sec}s, threshold: {expiry_threshold_sec}s)")

    while not _shutdown_event.is_set():
        start_time = time.time()
        expired_count = 0

        try:
            current_time = int(start_time)
            cutoff_time = current_time - expiry_threshold_sec

            # Query all allocated sandboxes
            response = db_client.table.query(
                IndexName=settings.ddb_gsi1_name,
                KeyConditionExpression="#status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": SandboxStatus.ALLOCATED.value},
            )

            allocated_sandboxes = [
                db_client._from_item(item) for item in response.get("Items", [])
            ]

            # Mark expired allocations
            for sandbox in allocated_sandboxes:
                if sandbox.allocated_at and sandbox.allocated_at < cutoff_time:
                    # Orphaned allocation - mark for deletion
                    sandbox.status = SandboxStatus.PENDING_DELETION
                    sandbox.deletion_requested_at = current_time
                    sandbox.updated_at = current_time
                    await db_client.put_sandbox(sandbox)
                    expired_count += 1
                    print(f"[{job_name}] Expired orphaned allocation: {sandbox.sandbox_id} (allocated at {sandbox.allocated_at})")

            duration_ms = int((time.time() - start_time) * 1000)

            # Update metrics
            expiry_total.labels(outcome="success").inc()
            if expired_count > 0:
                expiry_orphaned.inc(expired_count)

            log_request(
                request_id=f"job-expiry-{current_time}",
                action="background_expiry",
                outcome="success",
                latency_ms=duration_ms,
                message=f"Checked {len(allocated_sandboxes)} allocations, expired {expired_count} orphaned",
            )
        except Exception as e:
            expiry_total.labels(outcome="error").inc()
            log_request(
                request_id=f"job-expiry-{int(time.time())}",
                action="background_expiry",
                outcome="error",
                error=str(e),
                message=f"Auto-expiry job failed: {e}",
            )

        # Wait for next interval (or shutdown)
        try:
            await asyncio.wait_for(
                _shutdown_event.wait(),
                timeout=settings.auto_expiry_interval_sec
            )
            break  # Shutdown requested
        except asyncio.TimeoutError:
            continue  # Normal interval timeout, run again


def start_background_jobs():
    """
    Start all background jobs as asyncio tasks.

    Called during application startup.
    """
    global _shutdown_event, _scheduler_tasks

    _shutdown_event = asyncio.Event()

    # Create tasks for each job
    _scheduler_tasks = [
        asyncio.create_task(sync_job(), name="sync_job"),
        asyncio.create_task(cleanup_job(), name="cleanup_job"),
        asyncio.create_task(auto_expiry_job(), name="auto_expiry_job"),
    ]

    print(f"✅ Started {len(_scheduler_tasks)} background jobs")


async def stop_background_jobs():
    """
    Stop all background jobs gracefully.

    Called during application shutdown.
    """
    global _shutdown_event, _scheduler_tasks

    if _shutdown_event:
        print("🛑 Stopping background jobs...")
        _shutdown_event.set()

        # Wait for all tasks to complete (with timeout)
        if _scheduler_tasks:
            await asyncio.wait(_scheduler_tasks, timeout=10.0)

        print("✅ All background jobs stopped")
