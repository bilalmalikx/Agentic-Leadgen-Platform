"""
API Dependencies
Shared dependencies for FastAPI routes
"""

from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Dict, Any

from app.core.database import get_session
from app.core.security import get_current_user, get_current_user_optional, verify_api_key_auth
from app.core.redis_client import get_redis
from app.core.config import settings
from app.services.lead_service import LeadService
from app.services.campaign_service import CampaignService
from app.services.enrichment_service import EnrichmentService
from app.services.scoring_service import ScoringService
from app.services.email_service import EmailService
from app.services.webhook_service import WebhookService
from app.services.analytics_service import AnalyticsService
from app.services.export_service import ExportService
from app.services.notification_service import NotificationService
from app.services.cache_service import CacheService
from app.guardrails.rate_limiter import RateLimiter
from app.guardrails.input_validator import InputValidator
from app.vector_store.lead_index import LeadIndex


# Database session dependency
async def get_db_session() -> AsyncSession:
    """Get database session"""
    async for session in get_session():
        return session


# Service dependencies
async def get_lead_service(
    db: AsyncSession = Depends(get_db_session)
) -> LeadService:
    """Get lead service instance"""
    return LeadService(db)


async def get_campaign_service(
    db: AsyncSession = Depends(get_db_session)
) -> CampaignService:
    """Get campaign service instance"""
    return CampaignService(db)


async def get_enrichment_service() -> EnrichmentService:
    """Get enrichment service instance"""
    return EnrichmentService()


async def get_scoring_service() -> ScoringService:
    """Get scoring service instance"""
    return ScoringService()


async def get_email_service() -> EmailService:
    """Get email service instance"""
    return EmailService()


async def get_webhook_service() -> WebhookService:
    """Get webhook service instance"""
    return WebhookService()


async def get_analytics_service(
    db: AsyncSession = Depends(get_db_session)
) -> AnalyticsService:
    """Get analytics service instance"""
    return AnalyticsService(db)


async def get_export_service() -> ExportService:
    """Get export service instance"""
    return ExportService()


async def get_notification_service() -> NotificationService:
    """Get notification service instance"""
    return NotificationService()


async def get_cache_service() -> CacheService:
    """Get cache service instance"""
    return CacheService()


# Utility dependencies
async def get_rate_limiter(request: Request) -> RateLimiter:
    """Get rate limiter instance with request context"""
    client_ip = request.client.host if request.client else "unknown"
    return RateLimiter(identifier=client_ip)


async def get_input_validator() -> InputValidator:
    """Get input validator instance"""
    return InputValidator()


async def get_lead_index() -> LeadIndex:
    """Get lead index instance for vector search"""
    return LeadIndex()


# Vector store dependencies
async def get_vector_client():
    """Get ChromaDB client"""
    from app.vector_store.vector_client import get_vector_client
    return await get_vector_client()


# Authentication dependencies (exported from security)
# These are re-exported for easier imports
__all__ = [
    "get_db_session",
    "get_current_user",
    "get_current_user_optional",
    "verify_api_key_auth",
    "get_lead_service",
    "get_campaign_service",
    "get_enrichment_service",
    "get_scoring_service",
    "get_email_service",
    "get_webhook_service",
    "get_analytics_service",
    "get_export_service",
    "get_notification_service",
    "get_cache_service",
    "get_rate_limiter",
    "get_input_validator",
    "get_lead_index",
    "get_vector_client",
    "get_redis"
]