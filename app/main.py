"""
FastAPI Application Entry Point
Production-ready with middleware, exception handlers, and lifecycle events
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging
from datetime import datetime

from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.database import init_db, close_db
from app.core.redis_client import init_redis, close_redis
from app.api.v1.router import api_router
from app.middleware.error_handler import global_exception_handler
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.logging_middleware import LoggingMiddleware
from app.middleware.rate_limit_middleware import RateLimitMiddleware
from app.utils.metrics import setup_metrics

# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Handles startup and shutdown events
    Runs when app starts and stops
    """
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.app_env}")
    
    # Initialize database connection pool
    await init_db()
    logger.info("Database connected")
    
    # Initialize Redis connection pool
    await init_redis()
    logger.info("Redis connected")
    
    # Initialize ChromaDB (vector store)
    from app.vector_store.vector_client import init_chroma
    await init_chroma()
    logger.info("ChromaDB connected")
    
    yield  # App runs here
    
    # Shutdown
    logger.info("Shutting down application...")
    await close_db()
    await close_redis()
    logger.info("All connections closed")


# Create FastAPI instance
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI-powered lead generation system with guardrails and MCP tools",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
    openapi_url="/openapi.json" if settings.app_env != "production" else None,
    lifespan=lifespan
)


# Add middleware (order matters - first added, first executed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts,
)

app.add_middleware(RequestIDMiddleware)  # Add unique ID to each request
app.add_middleware(LoggingMiddleware)     # Log all requests
app.add_middleware(RateLimitMiddleware)   # Rate limiting


# Global exception handlers
@app.exception_handler(Exception)
async def handle_global_exception(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions"""
    return await global_exception_handler(request, exc)


# Health check endpoint
@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint for load balancers and monitoring
    Returns status of all dependencies
    """
    from app.core.redis_client import get_redis_health
    from app.core.database import get_db_health
    from app.vector_store.vector_client import get_chroma_health
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "services": {
            "database": await get_db_health(),
            "redis": await get_redis_health(),
            "chromadb": await get_chroma_health()
        }
    }
    
    # If any service is unhealthy, overall status becomes unhealthy
    for service, status in health_status["services"].items():
        if status.get("status") != "healthy":
            health_status["status"] = "unhealthy"
            break
    
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=health_status, status_code=status_code)


# Readiness probe for Kubernetes/Docker
@app.get("/ready", tags=["Health"])
async def readiness_check():
    """
    Readiness probe - checks if app is ready to accept traffic
    """
    return {"status": "ready"}


# Include API routes
app.include_router(api_router, prefix="/api/v1")


# Setup Prometheus metrics
if settings.prometheus_enabled:
    setup_metrics(app)
    logger.info("Prometheus metrics enabled")


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "docs": "/docs" if settings.app_env != "production" else None,
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug
    )