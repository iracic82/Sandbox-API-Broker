"""Pydantic schemas for API requests and responses."""

from typing import Optional
from pydantic import BaseModel, Field
from app.models.sandbox import SandboxStatus


# Request Schemas
class AllocateRequest(BaseModel):
    """Request schema for sandbox allocation (body can be empty, uses headers)."""

    pass


class MarkForDeletionRequest(BaseModel):
    """Request schema for marking sandbox for deletion (body can be empty, uses headers)."""

    pass


# Response Schemas
class SandboxResponse(BaseModel):
    """Base sandbox response schema."""

    sandbox_id: str = Field(..., description="Unique sandbox identifier")
    name: str = Field(..., description="Human-readable sandbox name")
    external_id: str = Field(..., description="ENG CSP external identifier")
    status: SandboxStatus = Field(..., description="Current sandbox status")
    allocated_to_track: Optional[str] = Field(None, description="Track ID if allocated")
    allocated_at: Optional[int] = Field(None, description="Unix timestamp of allocation")
    expires_at: Optional[int] = Field(None, description="Unix timestamp when allocation expires")

    class Config:
        from_attributes = True


class AllocateResponse(BaseModel):
    """Response schema for successful allocation."""

    sandbox_id: str
    name: str
    external_id: str
    allocated_at: int
    expires_at: int

    class Config:
        from_attributes = True


class MarkForDeletionResponse(BaseModel):
    """Response schema for marking sandbox for deletion."""

    sandbox_id: str
    status: SandboxStatus
    deletion_requested_at: int

    class Config:
        from_attributes = True


class SandboxListResponse(BaseModel):
    """Response schema for listing sandboxes."""

    sandboxes: list[SandboxResponse]
    count: int
    cursor: Optional[str] = None


# Error Response Schema
class ErrorDetail(BaseModel):
    """Error detail schema."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    request_id: Optional[str] = Field(None, description="Request ID for tracking")
    retry_after: Optional[int] = Field(None, description="Seconds to wait before retry")


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: ErrorDetail

    class Config:
        from_attributes = True
