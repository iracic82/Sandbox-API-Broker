"""Admin API endpoints for sandbox management."""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from app.api.dependencies import verify_admin_token
from app.schemas.sandbox import SandboxListResponse, SandboxResponse
from app.services.admin import admin_service
from app.models.sandbox import SandboxStatus


router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get(
    "/sandboxes",
    response_model=SandboxListResponse,
    responses={
        200: {"description": "List of sandboxes"},
        401: {"description": "Unauthorized"},
        403: {"description": "Admin access required"},
    },
)
async def list_sandboxes(
    request: Request,
    status: Optional[SandboxStatus] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=100, description="Number of items per page"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    _token: str = Depends(verify_admin_token),
):
    """
    List all sandboxes with optional filtering and pagination.

    Admin only endpoint.

    Query Parameters:
    - status: Filter by status (available, allocated, pending_deletion, stale)
    - limit: Items per page (1-100, default 50)
    - cursor: Pagination cursor from previous response
    """
    result = await admin_service.list_sandboxes(
        status_filter=status,
        limit=limit,
        cursor=cursor,
    )

    return SandboxListResponse(
        sandboxes=[
            SandboxResponse(
                sandbox_id=sb.sandbox_id,
                name=sb.name,
                external_id=sb.external_id,
                status=sb.status,
                allocated_to_track=sb.allocated_to_track,
                allocated_at=sb.allocated_at,
                expires_at=sb.expires_at,
                track_name=sb.track_name,
            )
            for sb in result["sandboxes"]
        ],
        count=len(result["sandboxes"]),
        cursor=result.get("cursor"),
    )


@router.post(
    "/sync",
    responses={
        200: {"description": "Sync completed"},
        401: {"description": "Unauthorized"},
        403: {"description": "Admin access required"},
    },
)
async def trigger_sync(
    request: Request,
    _token: str = Depends(verify_admin_token),
):
    """
    Manually trigger ENG CSP sync.

    Admin only endpoint.

    This will:
    1. Fetch all sandboxes from ENG CSP tenant
    2. Upsert active sandboxes to DynamoDB
    3. Mark missing sandboxes as 'stale'
    """
    result = await admin_service.trigger_sync()

    return {
        "status": "completed",
        "synced": result.get("synced", 0),
        "marked_stale": result.get("marked_stale", 0),
        "duration_ms": result.get("duration_ms", 0),
    }


@router.post(
    "/cleanup",
    responses={
        200: {"description": "Cleanup completed"},
        401: {"description": "Unauthorized"},
        403: {"description": "Admin access required"},
    },
)
async def trigger_cleanup(
    request: Request,
    _token: str = Depends(verify_admin_token),
):
    """
    Manually trigger cleanup of pending_deletion sandboxes.

    Admin only endpoint.

    This will:
    1. Find all sandboxes with status='pending_deletion'
    2. Delete from ENG CSP tenant
    3. Remove from DynamoDB
    4. Handle failures with retry logic
    """
    result = await admin_service.trigger_cleanup()

    return {
        "status": "completed",
        "deleted": result.get("deleted", 0),
        "failed": result.get("failed", 0),
        "duration_ms": result.get("duration_ms", 0),
    }


@router.get("/stats")
async def get_stats(
    request: Request,
    _token: str = Depends(verify_admin_token),
):
    """
    Get sandbox pool statistics.

    Admin only endpoint.
    """
    stats = await admin_service.get_stats()

    return {
        "total": stats.get("total", 0),
        "available": stats.get("available", 0),
        "allocated": stats.get("allocated", 0),
        "pending_deletion": stats.get("pending_deletion", 0),
        "stale": stats.get("stale", 0),
        "deletion_failed": stats.get("deletion_failed", 0),
    }


@router.post(
    "/bulk-delete",
    responses={
        200: {"description": "Bulk delete completed"},
        401: {"description": "Unauthorized"},
        403: {"description": "Admin access required"},
    },
)
async def bulk_delete_sandboxes(
    request: Request,
    status: Optional[SandboxStatus] = Query(None, description="Delete sandboxes with this status (stale, deletion_failed)"),
    _token: str = Depends(verify_admin_token),
):
    """
    Bulk delete sandboxes from DynamoDB by status.

    Admin only endpoint.

    This will:
    1. Find all sandboxes with the specified status
    2. Delete them from DynamoDB only (NOT from CSP)
    3. Return count of deleted items

    Use cases:
    - Clean up stale sandboxes (no longer in CSP)
    - Remove deletion_failed sandboxes after manual CSP cleanup

    Query Parameters:
    - status: Status filter (stale, deletion_failed, etc.)
    """
    result = await admin_service.bulk_delete_by_status(status)

    return {
        "status": "completed",
        "deleted": result.get("deleted", 0),
        "duration_ms": result.get("duration_ms", 0),
    }


@router.post(
    "/auto-delete-stale",
    responses={
        200: {"description": "Auto-delete completed"},
        401: {"description": "Unauthorized"},
        403: {"description": "Admin access required"},
    },
)
async def auto_delete_stale_sandboxes(
    request: Request,
    grace_period_hours: int = Query(24, description="Grace period in hours before deletion"),
    _token: str = Depends(verify_admin_token),
):
    """
    Automatically delete stale sandboxes older than grace period.

    Stale sandboxes are those that no longer exist in CSP but remain in DynamoDB.
    This endpoint is called by the background job scheduler (daily at 2 AM).

    Query Parameters:
    - grace_period_hours: Hours to wait before deleting stale sandboxes (default: 24)

    Use cases:
    - Scheduled background job (runs daily)
    - Manual trigger for immediate cleanup with custom grace period
    """
    result = await admin_service.auto_delete_stale_sandboxes(grace_period_hours)

    return {
        "status": "completed",
        "deleted": result.get("deleted", 0),
        "duration_ms": result.get("duration_ms", 0),
        "grace_period_hours": result.get("grace_period_hours", 24),
    }
