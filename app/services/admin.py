"""Admin service for sandbox management, sync, and cleanup."""

import time
from typing import Optional, Dict, Any
from app.core.config import settings
from app.db.dynamodb import db_client
from app.models.sandbox import Sandbox, SandboxStatus
from app.services.eng_csp import eng_csp_service
from app.core.metrics import (
    sync_total,
    sync_sandboxes_synced,
    sync_sandboxes_stale,
    sync_duration,
    cleanup_total,
    cleanup_deleted,
    cleanup_failed,
    cleanup_duration,
)


class AdminService:
    """Service for admin operations."""

    def __init__(self):
        self.db = db_client

    async def list_sandboxes(
        self,
        status_filter: Optional[SandboxStatus] = None,
        limit: int = 50,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List sandboxes with optional filtering and pagination.

        Args:
            status_filter: Optional status to filter by
            limit: Max items to return
            cursor: Pagination cursor

        Returns:
            Dict with sandboxes list and optional next cursor
        """
        # Build query parameters
        query_params = {"Limit": limit}
        if cursor:
            query_params["ExclusiveStartKey"] = self._decode_cursor(cursor)

        if status_filter:
            # Query by status using GSI1
            query_params.update({
                "IndexName": settings.ddb_gsi1_name,
                "KeyConditionExpression": "#status = :status",
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {":status": status_filter.value},
            })
            response = self.db.table.query(**query_params)
        else:
            # Scan all sandboxes
            response = self.db.table.scan(**query_params)

        sandboxes = [self.db._from_item(item) for item in response.get("Items", [])]

        result = {"sandboxes": sandboxes}

        # Add pagination cursor if more items exist
        if "LastEvaluatedKey" in response:
            result["cursor"] = self._encode_cursor(response["LastEvaluatedKey"])

        return result

    async def trigger_sync(self) -> Dict[str, Any]:
        """
        Manually trigger ENG CSP sync.

        Returns:
            Dict with sync results
        """
        start_time = time.time()

        try:
            # Fetch sandboxes from ENG CSP
            eng_sandboxes = await eng_csp_service.fetch_sandboxes()

            synced_count = 0
            stale_count = 0

            # Get current sandbox IDs from DynamoDB
            current_sandboxes = await self._get_all_sandbox_ids()

            # Upsert active sandboxes from ENG
            for eng_sb in eng_sandboxes:
                sandbox = Sandbox(
                    sandbox_id=eng_sb["id"],
                    name=eng_sb.get("name", f"sandbox-{eng_sb['id']}"),
                    external_id=eng_sb.get("external_id", eng_sb["id"]),
                    status=SandboxStatus.AVAILABLE,
                    last_synced=int(time.time()),
                    created_at=eng_sb.get("created_at", int(time.time())),
                    updated_at=int(time.time()),
                )

                # Only upsert if not allocated or pending deletion
                existing = await self.db.get_sandbox(sandbox.sandbox_id)
                if not existing or existing.status in [
                    SandboxStatus.AVAILABLE,
                    SandboxStatus.STALE,
                ]:
                    await self.db.put_sandbox(sandbox)
                    synced_count += 1

                # Remove from current set (to find missing ones)
                current_sandboxes.discard(eng_sb["id"])

            # Mark missing sandboxes as stale (not in ENG anymore)
            for missing_id in current_sandboxes:
                existing = await self.db.get_sandbox(missing_id)
                if existing and existing.status == SandboxStatus.AVAILABLE:
                    existing.status = SandboxStatus.STALE
                    existing.updated_at = int(time.time())
                    await self.db.put_sandbox(existing)
                    stale_count += 1

            duration_sec = time.time() - start_time
            duration_ms = int(duration_sec * 1000)

            # Update metrics
            sync_total.labels(outcome="success").inc()
            sync_sandboxes_synced.inc(synced_count)
            sync_sandboxes_stale.inc(stale_count)
            sync_duration.observe(duration_sec)

            return {
                "synced": synced_count,
                "marked_stale": stale_count,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            sync_total.labels(outcome="error").inc()
            sync_duration.observe(time.time() - start_time)
            raise

    async def trigger_cleanup(self) -> Dict[str, Any]:
        """
        Manually trigger cleanup of pending_deletion sandboxes.

        Returns:
            Dict with cleanup results
        """
        start_time = time.time()

        try:
            # Find all pending_deletion sandboxes
            response = self.db.table.query(
                IndexName=settings.ddb_gsi1_name,
                KeyConditionExpression="#status = :status",
                ExpressionAttributeNames={"#status": "status"},
                ExpressionAttributeValues={":status": SandboxStatus.PENDING_DELETION.value},
            )

            pending_sandboxes = [
                self.db._from_item(item) for item in response.get("Items", [])
            ]

            deleted_count = 0
            failed_count = 0

            # Process in batches with throttling to avoid overwhelming ENG CSP API
            batch_size = settings.cleanup_batch_size
            batch_delay = settings.cleanup_batch_delay_sec

            for i in range(0, len(pending_sandboxes), batch_size):
                batch = pending_sandboxes[i:i + batch_size]

                for sandbox in batch:
                    try:
                        # Delete from ENG CSP (uses external_id to extract UUID)
                        success = await eng_csp_service.delete_sandbox(sandbox.external_id)

                        if success:
                            # Remove from DynamoDB
                            self.db.table.delete_item(
                                Key={"PK": f"SBX#{sandbox.sandbox_id}", "SK": "META"}
                            )
                            deleted_count += 1
                            cleanup_deleted.inc()
                        else:
                            # Mark as failed
                            sandbox.status = SandboxStatus.DELETION_FAILED
                            sandbox.deletion_retry_count += 1
                            sandbox.updated_at = int(time.time())
                            await self.db.put_sandbox(sandbox)
                            failed_count += 1
                            cleanup_failed.inc()

                    except Exception as e:
                        # Handle deletion failure
                        sandbox.status = SandboxStatus.DELETION_FAILED
                        sandbox.deletion_retry_count += 1
                        sandbox.updated_at = int(time.time())
                        await self.db.put_sandbox(sandbox)
                        failed_count += 1
                        cleanup_failed.inc()
                        print(f"Failed to delete {sandbox.sandbox_id}: {e}")

                # Throttling: delay between batches (unless this is the last batch)
                if i + batch_size < len(pending_sandboxes):
                    import asyncio
                    await asyncio.sleep(batch_delay)

            duration_sec = time.time() - start_time
            duration_ms = int(duration_sec * 1000)

            # Update metrics
            cleanup_total.labels(outcome="success").inc()
            cleanup_duration.observe(duration_sec)

            return {
                "deleted": deleted_count,
                "failed": failed_count,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            cleanup_total.labels(outcome="error").inc()
            cleanup_duration.observe(time.time() - start_time)
            raise

    async def get_stats(self) -> Dict[str, int]:
        """
        Get sandbox pool statistics.

        Returns:
            Dict with counts by status
        """
        stats = {
            "total": 0,
            "available": 0,
            "allocated": 0,
            "pending_deletion": 0,
            "stale": 0,
            "deletion_failed": 0,
        }

        # Scan all sandboxes (in production, use CloudWatch metrics instead)
        response = self.db.table.scan()

        for item in response.get("Items", []):
            stats["total"] += 1
            status = item.get("status")
            if status in stats:
                stats[status] += 1

        return stats

    async def bulk_delete_by_status(
        self, status_filter: Optional[SandboxStatus] = None
    ) -> Dict[str, Any]:
        """
        Bulk delete sandboxes from DynamoDB by status.

        This ONLY deletes from DynamoDB, NOT from CSP.
        Use this to clean up stale or failed sandboxes.

        Args:
            status_filter: Status to filter by (e.g., 'stale', 'deletion_failed')

        Returns:
            Dict with deleted count and duration
        """
        start_time = time.time()
        deleted_count = 0

        try:
            # Query sandboxes by status using GSI1
            if status_filter:
                response = self.db.table.query(
                    IndexName="StatusIndex",
                    KeyConditionExpression="#status = :status",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={":status": status_filter.value},
                )
            else:
                # If no filter, scan all (dangerous, but allowed for admin)
                response = self.db.table.scan()

            items = response.get("Items", [])

            # Handle pagination
            while "LastEvaluatedKey" in response:
                if status_filter:
                    response = self.db.table.query(
                        IndexName="StatusIndex",
                        KeyConditionExpression="#status = :status",
                        ExpressionAttributeNames={"#status": "status"},
                        ExpressionAttributeValues={":status": status_filter.value},
                        ExclusiveStartKey=response["LastEvaluatedKey"],
                    )
                else:
                    response = self.db.table.scan(
                        ExclusiveStartKey=response["LastEvaluatedKey"]
                    )
                items.extend(response.get("Items", []))

            # Delete each item
            for item in items:
                sandbox_id = item.get("sandbox_id")
                if sandbox_id:
                    # Delete directly using DynamoDB table
                    self.db.table.delete_item(
                        Key={
                            "PK": f"SBX#{sandbox_id}",
                            "SK": "META",
                        }
                    )
                    deleted_count += 1
                    print(f"Deleted sandbox {sandbox_id} from DynamoDB")

            duration_ms = int((time.time() - start_time) * 1000)

            return {
                "deleted": deleted_count,
                "duration_ms": duration_ms,
            }
        except Exception as e:
            print(f"Bulk delete failed: {e}")
            raise

    async def _get_all_sandbox_ids(self) -> set:
        """Get all sandbox IDs from DynamoDB."""
        sandbox_ids = set()
        response = self.db.table.scan(ProjectionExpression="sandbox_id")

        for item in response.get("Items", []):
            sandbox_ids.add(item["sandbox_id"])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = self.db.table.scan(
                ProjectionExpression="sandbox_id",
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            for item in response.get("Items", []):
                sandbox_ids.add(item["sandbox_id"])

        return sandbox_ids

    def _encode_cursor(self, key: dict) -> str:
        """Encode DynamoDB key as cursor."""
        import json
        import base64

        return base64.b64encode(json.dumps(key).encode()).decode()

    def _decode_cursor(self, cursor: str) -> dict:
        """Decode cursor to DynamoDB key."""
        import json
        import base64

        return json.loads(base64.b64decode(cursor.encode()).decode())


# Global admin service instance
admin_service = AdminService()
