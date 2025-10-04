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


async def get_track_id(x_track_id: str = Header(..., alias="X-Track-ID")) -> str:
    """Extract and validate track ID from header."""
    if not x_track_id or len(x_track_id.strip()) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_TRACK_ID", "message": "X-Track-ID header is required"},
        )
    return x_track_id.strip()


async def get_idempotency_key(
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")
) -> Optional[str]:
    """Extract optional idempotency key from header."""
    if idempotency_key:
        return idempotency_key.strip()
    return None
