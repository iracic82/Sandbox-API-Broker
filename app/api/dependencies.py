"""FastAPI dependencies for authentication and validation."""

from typing import Optional
from fastapi import Header, HTTPException, status
from app.core.config import settings


async def verify_track_token(authorization: str = Header(...)) -> str:
    """Verify track bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid authorization header format"},
        )

    token = authorization.replace("Bearer ", "")
    if token != settings.broker_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid bearer token"},
        )

    return token


async def verify_admin_token(authorization: str = Header(...)) -> str:
    """Verify admin bearer token."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Invalid authorization header format"},
        )

    token = authorization.replace("Bearer ", "")
    if token != settings.broker_admin_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "FORBIDDEN", "message": "Admin access required"},
        )

    return token


async def get_instruqt_sandbox_id(
    x_instruqt_sandbox_id: Optional[str] = Header(None, alias="X-Instruqt-Sandbox-ID"),
    x_track_id: Optional[str] = Header(None, alias="X-Track-ID"),
) -> str:
    """
    Extract and validate Instruqt sandbox ID (unique per student).

    Supports two header formats for backward compatibility:
    - X-Instruqt-Sandbox-ID (preferred): Instruqt's unique sandbox instance ID
    - X-Track-ID (legacy): Falls back to this if new header not provided

    The sandbox ID uniquely identifies a student's sandbox instance, not the lab/track.
    """
    # Prefer new header, fall back to legacy
    sandbox_id = x_instruqt_sandbox_id or x_track_id

    if not sandbox_id or len(sandbox_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "MISSING_SANDBOX_ID",
                "message": "Either X-Instruqt-Sandbox-ID or X-Track-ID header is required"
            },
        )
    return sandbox_id.strip()


async def get_instruqt_track_id(
    x_instruqt_track_id: Optional[str] = Header(None, alias="X-Instruqt-Track-ID")
) -> Optional[str]:
    """
    Extract optional Instruqt track ID (lab identifier).

    This identifies the lab/track itself (e.g., "aws-security-101"), not the student instance.
    Used for grouping and analytics, not for allocation keys.
    """
    if x_instruqt_track_id:
        return x_instruqt_track_id.strip()
    return None


async def get_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> Optional[str]:
    """Extract optional idempotency key from header."""
    if idempotency_key:
        return idempotency_key.strip()
    return None


async def get_sandbox_name_prefix(
    x_sandbox_name_prefix: Optional[str] = Header(None, alias="X-Sandbox-Name-Prefix")
) -> Optional[str]:
    """
    Extract optional sandbox name prefix filter from header.

    When provided, the broker will only allocate sandboxes whose names start with this prefix.
    This allows different labs to use different subsets of the sandbox pool.

    Examples:
    - X-Sandbox-Name-Prefix: lab-adventure → matches lab-adventure-100, lab-adventure-xyz
    - X-Sandbox-Name-Prefix: start-lab → matches start-lab-test, start-lab-prod-123
    """
    if x_sandbox_name_prefix:
        return x_sandbox_name_prefix.strip()
    return None
