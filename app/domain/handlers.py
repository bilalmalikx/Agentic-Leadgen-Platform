"""
Domain Event Handlers
Business logic triggered by domain events
"""

from typing import Dict, Any, Optional
from uuid import UUID
from datetime import datetime

from app.core.logging import get_logger
from app.core.config import settings
from app.domain.events import (
    EventHandler, DomainEvent, EventType,
    LeadQualifiedEvent, CampaignCompletedEvent, EmailSentEvent,
    ScrapingJobCompletedEvent, LeadCreatedEvent
)
from app.domain.events import get_event_bus

logger = get_logger(__name__)


# ============================================
# Lead Event Handlers
# ============================================

class LeadCreatedHandler(EventHandler):
    """Handle lead creation events"""
    
    async def handle(self, event: DomainEvent):
        """When a lead is created, trigger enrichment and scoring"""
        lead_id = event.aggregate_id
        lead_data = event.data
        
        logger.info(f"Handling lead created event for {lead_id}")
        
        try:
            # Trigger enrichment in background
            from app.workers.enrichment_tasks import enrich_single_lead_task
            enrich_single_lead_task.delay(str(lead_id))
            
            # Trigger scoring in background
            from app.workers.lead_tasks import score_leads_task
            score_leads_task.delay([str(lead_id)], recalculate=True)
            
            # Add to vector store
            from app.vector_store.lead_index import add_lead_to_index
            from app.db.repositories.lead_repository import LeadRepository
            from app.core.database import get_sync_session
            
            with get_sync_session() as db:
                repo = LeadRepository(db)
                lead = repo.get_by_id(lead_id)
                if lead:
                    await add_lead_to_index(lead)
            
        except Exception as e:
            logger.error(f"Failed to handle lead created event for {lead_id}: {e}")


class LeadQualifiedHandler(EventHandler):
    """Handle lead qualification events"""
    
    async def handle(self, event: DomainEvent):
        """When a lead is qualified, trigger notifications and webhooks"""
        lead_id = event.aggregate_id
        score = event.data.get("score", 0)
        reasoning = event.data.get("reasoning", [])
        
        logger.info(f"Handling lead qualified event for {lead_id} with score {score}")
        
        try:
            # Get lead and campaign details
            from app.db.repositories.lead_repository import LeadRepository
            from app.db.repositories.campaign_repository import CampaignRepository
            from app.core.database import get_sync_session
            
            with get_sync_session() as db:
                lead_repo = LeadRepository(db)
                lead = lead_repo.get_by_id(lead_id)
                
                if lead and lead.campaign_id:
                    campaign_repo = CampaignRepository(db)
                    campaign = campaign_repo.get_by_id(lead.campaign_id)
                    
                    if campaign and campaign.created_by:
                        # Send notification to user
                        from app.services.notification_service import NotificationService
                        
                        notification_service = NotificationService()
                        await notification_service.notify_lead_qualified(
                            lead_id=lead_id,
                            lead_email=lead.email,
                            score=score,
                            campaign_name=campaign.name,
                            user_id=campaign.created_by
                        )
                        
                        # Trigger webhook
                        from app.workers.webhook_tasks import broadcast_webhook_event
                        broadcast_webhook_event.delay(
                            event_type="lead.qualified",
                            payload={
                                "lead_id": str(lead_id),
                                "email": lead.email,
                                "score": score,
                                "reasoning": reasoning,
                                "campaign_id": str(lead.campaign_id)
                            },
                            campaign_id=str(lead.campaign_id),
                            lead_id=str(lead_id)
                        )
            
        except Exception as e:
            logger.error(f"Failed to handle lead qualified event for {lead_id}: {e}")


# ============================================
# Campaign Event Handlers
# ============================================

class CampaignStartedHandler(EventHandler):
    """Handle campaign start events"""
    
    async def handle(self, event: DomainEvent):
        """When a campaign starts, trigger lead generation"""
        campaign_id = event.aggregate_id
        campaign_name = event.data.get("campaign_name")
        query = event.data.get("query")
        
        logger.info(f"Handling campaign started event for {campaign_id}")
        
        try:
            # Trigger lead generation task
            from app.workers.lead_tasks import generate_leads_task
            generate_leads_task.delay(str(campaign_id))
            
            # Send notification
            from app.db.repositories.campaign_repository import CampaignRepository
            from app.core.database import get_sync_session
            from app.services.notification_service import NotificationService
            
            with get_sync_session() as db:
                campaign_repo = CampaignRepository(db)
                campaign = campaign_repo.get_by_id(campaign_id)
                
                if campaign and campaign.created_by:
                    notification_service = NotificationService()
                    await notification_service.notify_campaign_started(
                        campaign_id=campaign_id,
                        campaign_name=campaign_name,
                        user_id=campaign.created_by
                    )
            
        except Exception as e:
            logger.error(f"Failed to handle campaign started event for {campaign_id}: {e}")


class CampaignCompletedHandler(EventHandler):
    """Handle campaign completion events"""
    
    async def handle(self, event: DomainEvent):
        """When a campaign completes, generate export and send notifications"""
        campaign_id = event.aggregate_id
        campaign_name = event.data.get("campaign_name")
        total_leads = event.data.get("total_leads", 0)
        
        logger.info(f"Handling campaign completed event for {campaign_id}")
        
        try:
            from app.db.repositories.campaign_repository import CampaignRepository
            from app.db.repositories.lead_repository import LeadRepository
            from app.core.database import get_sync_session
            from app.services.notification_service import NotificationService
            from app.services.export_service import ExportService
            
            with get_sync_session() as db:
                campaign_repo = CampaignRepository(db)
                campaign = campaign_repo.get_by_id(campaign_id)
                
                if campaign and campaign.created_by:
                    # Send notification
                    notification_service = NotificationService()
                    
                    # Check if auto-export is enabled
                    if campaign.auto_export:
                        export_service = ExportService()
                        download_url = await export_service.export_campaign_sync(
                            campaign_id=campaign_id,
                            format=campaign.export_format,
                            user_id=campaign.created_by
                        )
                    else:
                        download_url = None
                    
                    await notification_service.notify_campaign_completed(
                        campaign_id=campaign_id,
                        campaign_name=campaign_name,
                        total_leads=total_leads,
                        user_id=campaign.created_by,
                        download_url=download_url
                    )
                    
                    # Trigger webhook
                    from app.workers.webhook_tasks import broadcast_webhook_event
                    broadcast_webhook_event.delay(
                        event_type="campaign.completed",
                        payload={
                            "campaign_id": str(campaign_id),
                            "campaign_name": campaign_name,
                            "total_leads": total_leads,
                            "download_url": download_url
                        },
                        campaign_id=str(campaign_id)
                    )
            
        except Exception as e:
            logger.error(f"Failed to handle campaign completed event for {campaign_id}: {e}")


class CampaignFailedHandler(EventHandler):
    """Handle campaign failure events"""
    
    async def handle(self, event: DomainEvent):
        """When a campaign fails, send alert notification"""
        campaign_id = event.aggregate_id
        campaign_name = event.data.get("campaign_name")
        error = event.data.get("error", "Unknown error")
        
        logger.info(f"Handling campaign failed event for {campaign_id}")
        
        try:
            from app.db.repositories.campaign_repository import CampaignRepository
            from app.core.database import get_sync_session
            from app.services.notification_service import NotificationService
            
            with get_sync_session() as db:
                campaign_repo = CampaignRepository(db)
                campaign = campaign_repo.get_by_id(campaign_id)
                
                if campaign and campaign.created_by:
                    notification_service = NotificationService()
                    await notification_service.notify_campaign_failed(
                        campaign_id=campaign_id,
                        campaign_name=campaign_name,
                        error_message=error,
                        user_id=campaign.created_by
                    )
            
        except Exception as e:
            logger.error(f"Failed to handle campaign failed event for {campaign_id}: {e}")


# ============================================
# Scraping Event Handlers
# ============================================

class ScrapingJobCompletedHandler(EventHandler):
    """Handle scraping job completion events"""
    
    async def handle(self, event: DomainEvent):
        """When a scraping job completes, update campaign progress"""
        job_id = event.aggregate_id
        source = event.data.get("source")
        items_scraped = event.data.get("items_scraped", 0)
        campaign_id = event.data.get("campaign_id")
        
        logger.info(f"Handling scraping job completed event for {job_id}")
        
        if campaign_id:
            try:
                from app.db.repositories.campaign_repository import CampaignRepository
                from app.core.database import get_sync_session
                
                with get_sync_session() as db:
                    campaign_repo = CampaignRepository(db)
                    campaign = campaign_repo.get_by_id(UUID(campaign_id))
                    
                    if campaign:
                        # Update campaign progress
                        campaign.total_leads_found += items_scraped
                        campaign.update_progress()
                        db.commit()
                        
                        logger.info(f"Updated campaign {campaign_id} progress: {campaign.progress_percentage}%")
                        
            except Exception as e:
                logger.error(f"Failed to update campaign progress: {e}")


# ============================================
# Email Event Handlers
# ============================================

class EmailSentHandler(EventHandler):
    """Handle email sent events"""
    
    async def handle(self, event: DomainEvent):
        """When an email is sent, update lead engagement"""
        lead_id = event.aggregate_id
        provider_message_id = event.data.get("provider_message_id")
        
        logger.info(f"Handling email sent event for lead {lead_id}")
        
        try:
            from app.db.repositories.lead_repository import LeadRepository
            from app.core.database import get_sync_session
            
            with get_sync_session() as db:
                lead_repo = LeadRepository(db)
                lead = lead_repo.get_by_id(lead_id)
                
                if lead:
                    # Update lead status to contacted
                    lead_repo.update(lead_id, {"status": "contacted"})
                    logger.info(f"Lead {lead_id} status updated to contacted")
            
        except Exception as e:
            logger.error(f"Failed to handle email sent event for {lead_id}: {e}")


class EmailOpenedHandler(EventHandler):
    """Handle email opened events (from webhook)"""
    
    async def handle(self, event: DomainEvent):
        """When an email is opened, update lead engagement metrics"""
        lead_id = event.aggregate_id
        opened_at = event.data.get("opened_at")
        
        logger.info(f"Handling email opened event for lead {lead_id}")
        
        try:
            from app.db.repositories.lead_repository import LeadRepository
            from app.core.database import get_sync_session
            
            with get_sync_session() as db:
                lead_repo = LeadRepository(db)
                lead = lead_repo.get_by_id(lead_id)
                
                if lead:
                    lead_repo.update(lead_id, {
                        "email_opened_count": (lead.email_opened_count or 0) + 1,
                        "metadata": {**lead.metadata, "last_opened_at": opened_at}
                    })
                    logger.info(f"Lead {lead_id} email opened count: {lead.email_opened_count + 1}")
            
        except Exception as e:
            logger.error(f"Failed to handle email opened event for {lead_id}: {e}")


# ============================================
# System Event Handlers
# ============================================

class SystemErrorHandler(EventHandler):
    """Handle system error events"""
    
    async def handle(self, event: DomainEvent):
        """When a system error occurs, log and alert"""
        error = event.data.get("error", "Unknown error")
        context = event.data.get("context", {})
        
        logger.error(f"System error: {error}, context: {context}")
        
        # Send alert to monitoring system
        # (e.g., Slack, PagerDuty, Sentry)
        try:
            from app.services.notification_service import NotificationService
            
            notification_service = NotificationService()
            
            # Send to admin Slack channel if configured
            admin_webhook = getattr(settings, "ADMIN_SLACK_WEBHOOK", None)
            if admin_webhook:
                await notification_service._send_slack_notification(
                    webhook_url=admin_webhook,
                    title="🚨 System Error Alert",
                    message=f"Error: {error[:500]}\n\nContext: {context}",
                    data={"timestamp": datetime.utcnow().isoformat()}
                )
        except Exception as e:
            logger.error(f"Failed to send error alert: {e}")


# ============================================
# Register All Handlers
# ============================================

async def register_all_handlers():
    """Register all event handlers with the event bus"""
    bus = get_event_bus()
    
    # Lead handlers
    bus.subscribe(EventType.LEAD_CREATED, LeadCreatedHandler())
    bus.subscribe(EventType.LEAD_QUALIFIED, LeadQualifiedHandler())
    
    # Campaign handlers
    bus.subscribe(EventType.CAMPAIGN_STARTED, CampaignStartedHandler())
    bus.subscribe(EventType.CAMPAIGN_COMPLETED, CampaignCompletedHandler())
    bus.subscribe(EventType.CAMPAIGN_FAILED, CampaignFailedHandler())
    
    # Scraping handlers
    bus.subscribe(EventType.SCRAPING_JOB_COMPLETED, ScrapingJobCompletedHandler())
    
    # Email handlers
    bus.subscribe(EventType.EMAIL_SENT, EmailSentHandler())
    bus.subscribe(EventType.EMAIL_OPENED, EmailOpenedHandler())
    
    # System handlers
    bus.subscribe(EventType.SYSTEM_ERROR, SystemErrorHandler())
    
    logger.info("All domain event handlers registered")
    
    # Start event bus
    await bus.start()