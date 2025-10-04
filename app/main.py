"""FastAPI application entry point."""

import uuid
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import router
from app.api.admin_routes import router as admin_router
from app.api.metrics_routes import router as metrics_router
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.jobs import start_background_jobs, stop_background_jobs
from app import __version__


# Create FastAPI app with enhanced OpenAPI documentation
app = FastAPI(
    title="Sandbox Broker API",
    description="""
## High-Concurrency Sandbox Allocation Service

Production-grade API for allocating pre-created CSP sandboxes to Instruqt tracks with zero double-allocations.

### Key Features

* **Atomic Allocation**: K-candidate strategy with conditional writes
* **Idempotency**: Safe retries via X-Track-ID header
* **Auto-Expiry**: Automatic cleanup after 4.5 hours
* **Circuit Breaker**: Protection against CSP API failures
* **Observability**: Prometheus metrics, structured logging
* **Security**: Rate limiting, OWASP headers, authentication

### Workflow

1. **Allocate**: Track requests sandbox via POST /v1/allocate
2. **Use**: Student uses sandbox for lab (up to 4 hours)
3. **Mark for Deletion**: Track calls POST /v1/sandboxes/{id}/mark-for-deletion when student stops
4. **Cleanup**: Background job deletes from CSP within ~5 minutes
5. **Safety Net**: Auto-expiry after 4.5h if track crashes

### Authentication

All endpoints require Bearer token authentication:
- **Track Endpoints**: Use `BROKER_API_TOKEN`
- **Admin Endpoints**: Use `BROKER_ADMIN_TOKEN`

Example: `Authorization: Bearer your_token_here`
    """,
    version=__version__,
    docs_url=f"{settings.api_base_path}/docs",
    redoc_url=f"{settings.api_base_path}/redoc",
    openapi_url=f"{settings.api_base_path}/openapi.json",
    contact={
        "name": "Sandbox Broker API",
        "url": "https://github.com/iracic82/Sandbox-API-Broker",
    },
    license_info={
        "name": "MIT",
    },
    openapi_tags=[
        {
            "name": "Sandboxes",
            "description": "Track endpoints for allocating and managing sandboxes",
        },
        {
            "name": "Admin",
            "description": "Admin endpoints for pool management and operations",
        },
        {
            "name": "Observability",
            "description": "Health checks and metrics",
        },
    ],
)

# Add middleware (order matters: first added = outermost layer)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware, requests_per_second=10, burst=20)
app.add_middleware(LoggingMiddleware)

# CORS configuration (restrictive for production API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production: replace with specific origins
    allow_credentials=False,  # No cookies for this API
    allow_methods=["GET", "POST"],  # Only needed methods
    allow_headers=["Authorization", "Content-Type", "X-Track-ID", "Idempotency-Key"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    max_age=3600,  # Cache preflight for 1 hour
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
                "request_id": str(uuid.uuid4()),
            }
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "request_id": str(uuid.uuid4()),
            }
        },
    )


# Include routers
app.include_router(router, prefix=settings.api_base_path, tags=["sandboxes"])
app.include_router(admin_router, prefix=settings.api_base_path, tags=["admin"])
app.include_router(metrics_router, tags=["observability"])


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Sandbox Broker API",
        "version": __version__,
        "docs": f"{settings.api_base_path}/docs",
    }


# Startup/shutdown events
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    print(f"🚀 Sandbox Broker API v{__version__} starting...")
    print(f"📍 API base path: {settings.api_base_path}")
    print(f"🗄️  DynamoDB table: {settings.ddb_table_name}")
    if settings.ddb_endpoint_url:
        print(f"🔧 Using local DynamoDB: {settings.ddb_endpoint_url}")

    # Start background jobs
    print(f"⏱️  Background jobs:")
    print(f"   - Sync: every {settings.sync_interval_sec}s")
    print(f"   - Cleanup: every {settings.cleanup_interval_sec}s")
    print(f"   - Auto-expiry: every {settings.auto_expiry_interval_sec}s")
    start_background_jobs()


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("👋 Sandbox Broker API shutting down...")
    await stop_background_jobs()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level=settings.log_level.lower(),
    )
