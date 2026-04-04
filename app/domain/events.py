"""
Domain Events
Event-driven architecture for decoupled communication between services
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
from enum import Enum
import asyncio
from abc import ABC, abstractmethod

from app.core.logging import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Types of domain events"""
    # Lead Events
    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    LEAD_DELETED = "lead.deleted"
    LEAD_QUALIFIED = "lead.qualified"
    LEAD_CONVERTED = "lead.converted"
    LEAD_SCORED = "lead.scored"
    LEAD_ENRICHED = "lead.enriched"
    LEAD_DUPLICATE_FOUND = "lead.duplicate.found"
    
    # Campaign Events
    CAMPAIGN_CREATED = "campaign.created"
    CAMPAIGN_STARTED = "campaign.started"
    CAMPAIGN_PAUSED = "campaign.paused"
    CAMPAIGN_RESUMED = "campaign.resumed"
    CAMPAIGN_COMPLETED = "campaign.completed"
    CAMPAIGN_FAILED = "campaign.failed"
    CAMPAIGN_CANCELLED = "campaign.cancelled"
    
    # Scraping Events
    SCRAPING_JOB_STARTED = "scraping.job.started"
    SCRAPING_JOB_COMPLETED = "scraping.job.completed"
    SCRAPING_JOB_FAILED = "scraping.job.failed"
    SCRAPING_RATE_LIMIT_HIT = "scraping.rate_limit.hit"
    
    # Email Events
    EMAIL_SENT = "email.sent"
    EMAIL_DELIVERED = "email.delivered"
    EMAIL_OPENED = "email.opened"
    EMAIL_CLICKED = "email.clicked"
    EMAIL_BOUNCED = "email.bounced"
    
    # Webhook Events
    WEBHOOK_DELIVERED = "webhook.delivered"
    WEBHOOK_FAILED = "webhook.failed"
    
    # User Events
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_QUOTA_EXCEEDED = "user.quota.exceeded"
    
    # System Events
    SYSTEM_HEALTH_CHECK = "system.health.check"
    SYSTEM_ERROR = "system.error"
    SYSTEM_BACKUP_COMPLETED = "system.backup.completed"


@dataclass
class DomainEvent:
    """Base domain event class"""
    
    event_type: EventType
    aggregate_id: Optional[UUID] = None
    aggregate_type: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    event_id: UUID = field(default_factory=UUID.uuid4)
    user_id: Optional[UUID] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary"""
        return {
            "event_id": str(self.event_id),
            "event_type": self.event_type.value,
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "aggregate_type": self.aggregate_type,
            "data": self.data,
            "occurred_at": self.occurred_at.isoformat(),
            "user_id": str(self.user_id) if self.user_id else None,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id
        }


# ============================================
# Specific Event Classes
# ============================================

@dataclass
class LeadCreatedEvent(DomainEvent):
    """Event when a lead is created"""
    def __init__(self, lead_id: UUID, lead_data: Dict[str, Any], user_id: Optional[UUID] = None):
        super().__init__(
            event_type=EventType.LEAD_CREATED,
            aggregate_id=lead_id,
            aggregate_type="lead",
            data=lead_data,
            user_id=user_id
        )


@dataclass
class LeadQualifiedEvent(DomainEvent):
    """Event when a lead is qualified"""
    def __init__(self, lead_id: UUID, score: int, reasoning: List[str], user_id: Optional[UUID] = None):
        super().__init__(
            event_type=EventType.LEAD_QUALIFIED,
            aggregate_id=lead_id,
            aggregate_type="lead",
            data={
                "score": score,
                "reasoning": reasoning,
                "qualified_at": datetime.utcnow().isoformat()
            },
            user_id=user_id
        )


@dataclass
class CampaignStartedEvent(DomainEvent):
    """Event when a campaign starts"""
    def __init__(self, campaign_id: UUID, campaign_name: str, query: str, user_id: Optional[UUID] = None):
        super().__init__(
            event_type=EventType.CAMPAIGN_STARTED,
            aggregate_id=campaign_id,
            aggregate_type="campaign",
            data={
                "campaign_name": campaign_name,
                "query": query,
                "started_at": datetime.utcnow().isoformat()
            },
            user_id=user_id
        )


@dataclass
class CampaignCompletedEvent(DomainEvent):
    """Event when a campaign completes"""
    def __init__(self, campaign_id: UUID, campaign_name: str, total_leads: int, user_id: Optional[UUID] = None):
        super().__init__(
            event_type=EventType.CAMPAIGN_COMPLETED,
            aggregate_id=campaign_id,
            aggregate_type="campaign",
            data={
                "campaign_name": campaign_name,
                "total_leads": total_leads,
                "completed_at": datetime.utcnow().isoformat()
            },
            user_id=user_id
        )


@dataclass
class EmailSentEvent(DomainEvent):
    """Event when an email is sent"""
    def __init__(self, lead_id: UUID, to_email: str, subject: str, provider_message_id: str):
        super().__init__(
            event_type=EventType.EMAIL_SENT,
            aggregate_id=lead_id,
            aggregate_type="lead",
            data={
                "to_email": to_email,
                "subject": subject,
                "provider_message_id": provider_message_id,
                "sent_at": datetime.utcnow().isoformat()
            }
        )


@dataclass
class ScrapingJobCompletedEvent(DomainEvent):
    """Event when a scraping job completes"""
    def __init__(self, job_id: UUID, source: str, items_scraped: int, campaign_id: Optional[UUID] = None):
        super().__init__(
            event_type=EventType.SCRAPING_JOB_COMPLETED,
            aggregate_id=job_id,
            aggregate_type="scraping_job",
            data={
                "source": source,
                "items_scraped": items_scraped,
                "campaign_id": str(campaign_id) if campaign_id else None,
                "completed_at": datetime.utcnow().isoformat()
            }
        )


# ============================================
# Event Bus
# ============================================

class EventHandler(ABC):
    """Abstract event handler"""
    
    @abstractmethod
    async def handle(self, event: DomainEvent) -> None:
        """Handle the event"""
        pass


class EventBus:
    """
    Event bus for publishing and handling domain events
    Supports synchronous and asynchronous handlers
    """
    
    def __init__(self):
        self._handlers: Dict[EventType, List[EventHandler]] = {}
        self._event_queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False
        self._worker_task = None
    
    def subscribe(self, event_type: EventType, handler: EventHandler):
        """Subscribe a handler to an event type"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"Handler {handler.__class__.__name__} subscribed to {event_type.value}")
    
    def unsubscribe(self, event_type: EventType, handler: EventHandler):
        """Unsubscribe a handler from an event type"""
        if event_type in self._handlers:
            self._handlers[event_type].remove(handler)
            logger.debug(f"Handler {handler.__class__.__name__} unsubscribed from {event_type.value}")
    
    async def publish(self, event: DomainEvent):
        """
        Publish an event to all subscribed handlers
        Handlers are called in background
        """
        event_type = event.event_type
        
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    # Schedule handler in background
                    asyncio.create_task(handler.handle(event))
                    logger.debug(f"Event {event_type.value} published to {handler.__class__.__name__}")
                except Exception as e:
                    logger.error(f"Failed to publish event {event_type.value} to handler {handler.__class__.__name__}: {e}")
        
        # Also add to queue for persistence
        await self._event_queue.put(event)
    
    async def publish_sync(self, event: DomainEvent):
        """
        Publish an event synchronously (handlers run immediately)
        """
        event_type = event.event_type
        
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    await handler.handle(event)
                    logger.debug(f"Event {event_type.value} published synchronously to {handler.__class__.__name__}")
                except Exception as e:
                    logger.error(f"Failed to publish event {event_type.value} to handler {handler.__class__.__name__}: {e}")
    
    async def start(self):
        """Start the event bus worker"""
        self._is_running = True
        self._worker_task = asyncio.create_task(self._process_queue())
        logger.info("Event bus started")
    
    async def stop(self):
        """Stop the event bus worker"""
        self._is_running = False
        if self._worker_task:
            self._worker_task.cancel()
        logger.info("Event bus stopped")
    
    async def _process_queue(self):
        """Process events from queue"""
        while self._is_running:
            try:
                event = await self._event_queue.get()
                # Here you can persist events to database for audit
                await self._persist_event(event)
                self._event_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event queue: {e}")
    
    async def _persist_event(self, event: DomainEvent):
        """Persist event to database (for event sourcing)"""
        try:
            from app.db.session import get_sync_session
            from app.models.audit_log import AuditLog
            
            with get_sync_session() as db:
                audit_log = AuditLog(
                    action=event.event_type.value,
                    resource_type=event.aggregate_type or "event",
                    resource_id=str(event.aggregate_id) if event.aggregate_id else None,
                    new_value=event.data,
                    user_id=event.user_id,
                    metadata={"event_id": str(event.event_id), "correlation_id": event.correlation_id}
                )
                db.add(audit_log)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to persist event: {e}")


# ============================================
# Singleton Event Bus
# ============================================

_event_bus = None


def get_event_bus() -> EventBus:
    """Get or create event bus instance"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


async def publish_event(event: DomainEvent):
    """Quick function to publish an event"""
    bus = get_event_bus()
    await bus.publish(event)


# ============================================
# Example Handlers
# ============================================

class LeadQualifiedHandler(EventHandler):
    """Handler for lead qualified events"""
    
    async def handle(self, event: DomainEvent):
        logger.info(f"Lead {event.aggregate_id} was qualified with score {event.data.get('score')}")
        
        # Trigger actions based on qualification
        # - Send notification
        # - Add to outreach queue
        # - Update CRM
        pass


class CampaignCompletedHandler(EventHandler):
    """Handler for campaign completed events"""
    
    async def handle(self, event: DomainEvent):
        logger.info(f"Campaign {event.aggregate_id} completed with {event.data.get('total_leads')} leads")
        
        # Trigger actions based on completion
        # - Send email notification
        # - Generate export
        # - Update dashboard
        pass


class EmailSentHandler(EventHandler):
    """Handler for email sent events"""
    
    async def handle(self, event: DomainEvent):
        logger.info(f"Email sent to {event.data.get('to_email')} for lead {event.aggregate_id}")
        
        # Update lead engagement metrics
        pass


async def register_default_handlers():
    """Register all default event handlers"""
    bus = get_event_bus()
    
    bus.subscribe(EventType.LEAD_QUALIFIED, LeadQualifiedHandler())
    bus.subscribe(EventType.CAMPAIGN_COMPLETED, CampaignCompletedHandler())
    bus.subscribe(EventType.EMAIL_SENT, EmailSentHandler())
    
    logger.info("Default event handlers registered")