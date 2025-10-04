"""FastAPI application entry point."""

import uuid
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.api.routes import router
from app.api.admin_routes import router as admin_router
from app.middleware.logging import LoggingMiddleware
from app import __version__


# Create FastAPI app
app = FastAPI(
    title="Sandbox Broker API",
    description="High-concurrency sandbox allocation service for Instruqt tracks",
    version=__version__,
    docs_url=f"{settings.api_base_path}/docs",
    redoc_url=f"{settings.api_base_path}/redoc",
    openapi_url=f"{settings.api_base_path}/openapi.json",
)

# Add middleware
app.add_middleware(LoggingMiddleware)


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


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    print("👋 Sandbox Broker API shutting down...")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level=settings.log_level.lower(),
    )
