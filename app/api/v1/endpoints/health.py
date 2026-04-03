"""
Health Check Endpoints
For monitoring, load balancers, and Kubernetes probes
"""

from fastapi import APIRouter, Depends, status
from typing import Dict, Any
from datetime import datetime

from app.core.database import get_db_health
from app.core.redis_client import get_redis_health
from app.vector_store.vector_client import get_chroma_health
from app.core.config import settings
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Comprehensive health check endpoint
    Checks database, Redis, ChromaDB, and application health
    """
    # Check all service health
    db_health = await get_db_health()
    redis_health = await get_redis_health()
    chroma_health = await get_chroma_health()
    
    # Determine overall status
    services_healthy = all([
        db_health.get("status") == "healthy",
        redis_health.get("status") == "healthy",
        chroma_health.get("status") == "healthy"
    ])
    
    overall_status = "healthy" if services_healthy else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow().isoformat(),
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.app_env,
        services={
            "database": db_health,
            "redis": redis_health,
            "chromadb": chroma_health
        }
    )


@router.get("/live")
async def liveness_probe():
    """
    Liveness probe for container orchestration
    Returns 200 if app is running
    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/ready")
async def readiness_probe():
    """
    Readiness probe - checks if app is ready to accept traffic
    Returns 200 only when all dependencies are ready
    """
    db_health = await get_db_health()
    redis_health = await get_redis_health()
    
    if db_health.get("status") != "healthy":
        return {"status": "not ready", "reason": "database not ready"}, status.HTTP_503_SERVICE_UNAVAILABLE
    
    if redis_health.get("status") != "healthy":
        return {"status": "not ready", "reason": "redis not ready"}, status.HTTP_503_SERVICE_UNAVAILABLE
    
    return {"status": "ready"}


@router.get("/metrics")
async def metrics():
    """
    Simple metrics endpoint
    For Prometheus scraping (detailed metrics via prometheus_client)
    """
    from app.utils.metrics import get_metrics
    
    return get_metrics()


@router.get("/version")
async def version():
    """
    Get application version information
    """
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "python_version": "3.11"
    }