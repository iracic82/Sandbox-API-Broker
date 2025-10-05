"""API route handlers."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.api.dependencies import (
    verify_track_token,
    get_instruqt_sandbox_id,
    get_instruqt_track_id,
    get_idempotency_key,
)
from app.schemas.sandbox import (
    AllocateResponse,
    MarkForDeletionResponse,
    SandboxResponse,
    ErrorResponse,
)
from app.services.allocation import (
    allocation_service,
    NoSandboxesAvailableError,
    NotSandboxOwnerError,
    AllocationExpiredError,
)


router = APIRouter(
    tags=["Sandboxes"],
)


@router.post(
    "/allocate",
    response_model=AllocateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "Idempotent response - sandbox already allocated"},
        201: {"description": "New sandbox allocated"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        409: {"model": ErrorResponse, "description": "No sandboxes available"},
    },
)
async def allocate_sandbox(
    request: Request,
    instruqt_sandbox_id: str = Depends(get_instruqt_sandbox_id),
    instruqt_track_id: Optional[str] = Depends(get_instruqt_track_id),
    idempotency_key: Optional[str] = Depends(get_idempotency_key),
    _token: str = Depends(verify_track_token),
):
    """
    Allocate a sandbox to the requesting Instruqt sandbox instance.

    Headers:
    - Authorization: Bearer <token>
    - X-Instruqt-Sandbox-ID: <unique_sandbox_id> (preferred) OR X-Track-ID: <sandbox_id> (legacy)
    - X-Instruqt-Track-ID: <lab_identifier> (optional, for analytics)
    - Idempotency-Key: <optional_key> (defaults to sandbox_id)

    The X-Instruqt-Sandbox-ID should be the unique identifier for the student's sandbox instance,
    NOT the lab/track identifier. Multiple students can run the same lab simultaneously.
    """
    request_id = str(uuid.uuid4())

    try:
        sandbox = await allocation_service.allocate_sandbox(
            track_id=instruqt_sandbox_id,  # Internal code still uses 'track_id' variable name
            idempotency_key=idempotency_key,
            instruqt_track_id=instruqt_track_id,  # Pass optional lab identifier
        )

        # Check if this was idempotent (existing allocation)
        response_status = status.HTTP_200_OK if sandbox.idempotency_key == (idempotency_key or instruqt_sandbox_id) else status.HTTP_201_CREATED

        return AllocateResponse(
            sandbox_id=sandbox.sandbox_id,
            name=sandbox.name,
            external_id=sandbox.external_id,
            allocated_at=sandbox.allocated_at or 0,
            expires_at=sandbox.expires_at or 0,
        )

    except NoSandboxesAvailableError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "NO_SANDBOXES_AVAILABLE",
                "message": str(e),
                "request_id": request_id,
                "retry_after": 30,
            },
        )


@router.post(
    "/sandboxes/{sandbox_id}/mark-for-deletion",
    response_model=MarkForDeletionResponse,
    responses={
        200: {"description": "Sandbox marked for deletion"},
        403: {"model": ErrorResponse, "description": "Not owner or expired"},
        404: {"model": ErrorResponse, "description": "Sandbox not found"},
    },
)
async def mark_sandbox_for_deletion(
    sandbox_id: str,
    request: Request,
    instruqt_sandbox_id: str = Depends(get_instruqt_sandbox_id),
    _token: str = Depends(verify_track_token),
):
    """
    Mark sandbox for deletion when student stops lab.

    Headers:
    - Authorization: Bearer <token>
    - X-Instruqt-Sandbox-ID: <sandbox_id> (preferred) OR X-Track-ID: <sandbox_id> (legacy)
    """
    request_id = str(uuid.uuid4())

    try:
        sandbox = await allocation_service.mark_for_deletion(
            sandbox_id=sandbox_id,
            track_id=instruqt_sandbox_id,  # Internal code still uses 'track_id' variable name
        )

        return MarkForDeletionResponse(
            sandbox_id=sandbox.sandbox_id,
            status=sandbox.status,
            deletion_requested_at=sandbox.deletion_requested_at or 0,
        )

    except NotSandboxOwnerError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_SANDBOX_OWNER",
                "message": str(e),
                "request_id": request_id,
            },
        )

    except AllocationExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ALLOCATION_EXPIRED",
                "message": str(e),
                "request_id": request_id,
            },
        )


@router.get(
    "/sandboxes/{sandbox_id}",
    response_model=SandboxResponse,
    responses={
        200: {"description": "Sandbox details"},
        403: {"model": ErrorResponse, "description": "Not owner"},
        404: {"model": ErrorResponse, "description": "Sandbox not found"},
    },
)
async def get_sandbox(
    sandbox_id: str,
    request: Request,
    instruqt_sandbox_id: str = Depends(get_instruqt_sandbox_id),
    _token: str = Depends(verify_track_token),
):
    """
    Get sandbox details (must be owned by requesting Instruqt sandbox).

    Headers:
    - Authorization: Bearer <token>
    - X-Instruqt-Sandbox-ID: <sandbox_id> (preferred) OR X-Track-ID: <sandbox_id> (legacy)
    """
    request_id = str(uuid.uuid4())

    try:
        sandbox = await allocation_service.get_sandbox(
            sandbox_id=sandbox_id,
            track_id=instruqt_sandbox_id,  # Internal code still uses 'track_id' variable name
        )

        return SandboxResponse(
            sandbox_id=sandbox.sandbox_id,
            name=sandbox.name,
            external_id=sandbox.external_id,
            status=sandbox.status,
            allocated_to_track=sandbox.allocated_to_track,
            allocated_at=sandbox.allocated_at,
            expires_at=sandbox.expires_at,
        )

    except NotSandboxOwnerError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NOT_SANDBOX_OWNER",
                "message": str(e),
                "request_id": request_id,
            },
        )


@router.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@router.get("/readyz")
async def readiness_check():
    """Readiness check endpoint."""
    # TODO: Add DynamoDB connectivity check
    return {"status": "ready"}
