"""
Webhook Delivery Model
Tracks webhook delivery attempts and status
"""

from sqlalchemy import Column, String, Integer, JSON, Text, ForeignKey, Index, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import enum

from app.models.base import BaseModel


class WebhookStatus(enum.Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    DELIVERING = "delivering"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    EXPIRED = "expired"


class WebhookDelivery(BaseModel):
    """Webhook delivery tracking model"""
    
    __tablename__ = "webhook_deliveries"
    
    # Webhook configuration
    webhook_url = Column(String(500), nullable=False)
    webhook_id = Column(String(100), nullable=True, index=True)
    
    # Event details
    event_type = Column(String(100), nullable=False, index=True)
    event_data = Column(JSON, nullable=False)
    
    # Association
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True, index=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True, index=True)
    
    # Delivery status
    status = Column(Enum(WebhookStatus), default=WebhookStatus.PENDING, nullable=False, index=True)
    status_message = Column(Text, nullable=True)
    
    # Response details
    response_status_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)
    response_headers = Column(JSON, nullable=True)
    
    # Timing
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    # Retry logic
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=5, nullable=False)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    # Request details
    request_headers = Column(JSON, nullable=True)
    request_body = Column(Text, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_webhook_status_retry", "status", "next_retry_at"),
        Index("idx_webhook_event_time", "event_type", "created_at"),
        Index("idx_webhook_campaign", "campaign_id", "status"),
    )
    
    def mark_delivering(self):
        """Mark webhook as delivering"""
        self.status = WebhookStatus.DELIVERING
    
    def mark_success(self, status_code: int, response_body: str = None, response_headers: dict = None):
        """Mark webhook delivery as successful"""
        self.status = WebhookStatus.SUCCESS
        self.delivered_at = datetime.utcnow()
        self.response_status_code = status_code
        self.response_body = response_body
        self.response_headers = response_headers
    
    def mark_failed(self, status_code: int = None, error_message: str = None):
        """Mark webhook delivery as failed"""
        self.status = WebhookStatus.FAILED
        self.response_status_code = status_code
        self.status_message = error_message
    
    def schedule_retry(self):
        """Schedule retry with exponential backoff"""
        self.retry_count += 1
        
        if self.retry_count >= self.max_retries:
            self.status = WebhookStatus.EXPIRED
            return
        
        # Exponential backoff: 30s, 60s, 120s, 240s, 480s
        delay_seconds = 30 * (2 ** (self.retry_count - 1))
        self.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
        self.status = WebhookStatus.RETRYING
    
    def can_retry(self) -> bool:
        """Check if webhook can be retried"""
        return self.retry_count < self.max_retries and self.status in [
            WebhookStatus.FAILED,
            WebhookStatus.RETRYING
        ]
    
    def get_summary(self) -> dict:
        """Get delivery summary"""
        return {
            "id": str(self.id),
            "event_type": self.event_type,
            "status": self.status.value if self.status else None,
            "url": self.webhook_url,
            "retry_count": self.retry_count,
            "status_code": self.response_status_code,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None
        }