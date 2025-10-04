"""Metrics and health check endpoints."""

from fastapi import APIRouter, Response
from fastapi.responses import JSONResponse
from app.core.metrics import get_metrics, update_pool_gauges
from app.db.dynamodb import db_client
import time

router = APIRouter()


@router.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus exposition format.
    """
    # Update pool gauges before returning metrics
    await update_pool_gauges(db_client)

    metrics_output, content_type = get_metrics()
    return Response(content=metrics_output, media_type=content_type)


@router.get("/healthz")
async def healthz():
    """
    Liveness probe.

    Returns 200 if the service is alive (process is running).
    Used by Kubernetes/ECS for liveness checks.
    """
    return {"status": "healthy", "timestamp": int(time.time())}


@router.get("/readyz")
async def readyz():
    """
    Readiness probe.

    Returns 200 if the service is ready to serve traffic.
    Checks DynamoDB connectivity.
    """
    try:
        # Quick DynamoDB check - scan with limit 1
        db_client.table.scan(Limit=1)
        return {
            "status": "ready",
            "timestamp": int(time.time()),
            "checks": {"dynamodb": "ok"},
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "timestamp": int(time.time()),
                "checks": {"dynamodb": f"error: {str(e)}"},
            },
        )
