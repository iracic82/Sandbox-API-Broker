"""Background worker for running scheduled jobs.

This is a separate service that runs background jobs independently from the API.
It prevents duplicate job execution when running multiple API instances for HA.

Usage:
    python -m app.jobs.worker
"""

import asyncio
import signal
import sys
from app.core.logging import log_request
from app.jobs import scheduler
from app import __version__


async def run_worker():
    """Run all background jobs in a single worker process."""
    print(f"🚀 Sandbox Broker Worker v{__version__} starting...")
    print("📋 Background jobs:")
    print("   - sync_job: Fetch sandboxes from CSP and sync to DynamoDB")
    print("   - cleanup_job: Delete pending_deletion sandboxes from CSP")
    print("   - auto_expiry_job: Mark expired allocations for deletion")
    print("   - auto_delete_stale_job: Clean up stale sandboxes")
    print()

    # Create shutdown event and set it in the scheduler module
    scheduler._shutdown_event = asyncio.Event()

    # Create tasks for each background job
    tasks = [
        asyncio.create_task(scheduler.sync_job(), name="sync_job"),
        asyncio.create_task(scheduler.cleanup_job(), name="cleanup_job"),
        asyncio.create_task(scheduler.auto_expiry_job(), name="auto_expiry_job"),
        asyncio.create_task(scheduler.auto_delete_stale_job(), name="auto_delete_stale_job"),
    ]

    print(f"✅ Started {len(tasks)} background jobs")
    print("Worker is running. Press Ctrl+C to stop.")
    print()

    # Setup signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        print("\n🛑 Shutdown signal received. Stopping background jobs...")
        scheduler._shutdown_event.set()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Wait for all tasks to complete (or shutdown signal)
        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        print(f"❌ Worker error: {e}")
        scheduler._shutdown_event.set()
    finally:
        # Wait for tasks to finish gracefully
        if tasks:
            await asyncio.wait(tasks, timeout=10.0)
        print("✅ All background jobs stopped")
        print("👋 Worker shutdown complete")


def main():
    """Main entry point for the worker."""
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print("\n👋 Worker stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Worker failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
