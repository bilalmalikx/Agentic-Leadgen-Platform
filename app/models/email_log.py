"""
Email Log Model - Tracks all emails sent from the system
For audit and compliance purposes
"""

from sqlalchemy import Column, String, Integer, JSON, Enum, Text, ForeignKey, Index, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models.base import BaseModel, AuditMixin


class EmailStatus(enum.Enum):
    """Email delivery status"""
    PENDING = "pending"
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    OPENED = "opened"
    CLICKED = "clicked"
    BOUNCED = "bounced"
    FAILED = "failed"
    SPAM = "spam"
    BLOCKED = "blocked"


class EmailType(enum.Enum):
    """Type of email"""
    OUTREACH = "outreach"  # Cold email to lead
    FOLLOWUP = "followup"  # Follow-up email
    NOTIFICATION = "notification"  # System notification
    ANALYTICS = "analytics"  # Analytics report
    ALERT = "alert"  # System alert
    VERIFICATION = "verification"  # Email verification


class EmailLog(BaseModel, AuditMixin):
    """Email Log model - tracks email communications"""
    
    __tablename__ = "email_logs"
    
    # Association
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False, index=True)
    lead = relationship("Lead", back_populates="email_logs")
    
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=True, index=True)
    
    # Email Details
    email_type = Column(Enum(EmailType), default=EmailType.OUTREACH, nullable=False)
    from_email = Column(String(255), nullable=False)
    to_email = Column(String(255), nullable=False, index=True)
    subject = Column(String(500), nullable=False)
    content = Column(Text, nullable=False)
    content_html = Column(Text, nullable=True)
    
    # Template Information
    template_id = Column(String(100), nullable=True)
    template_name = Column(String(255), nullable=True)
    template_variables = Column(JSON, default=dict, nullable=False)
    
    # Status Tracking
    status = Column(Enum(EmailStatus), default=EmailStatus.PENDING, nullable=False, index=True)
    status_message = Column(Text, nullable=True)
    
    # Provider Information
    provider = Column(String(50), default="sendgrid", nullable=False)  # sendgrid, resend, aws_ses
    provider_message_id = Column(String(255), nullable=True, index=True)
    
    # Timestamps
    queued_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    first_clicked_at = Column(DateTime(timezone=True), nullable=True)
    bounced_at = Column(DateTime(timezone=True), nullable=True)
    
    # Engagement Metrics
    open_count = Column(Integer, default=0)
    click_count = Column(Integer, default=0)
    
    # Retry Information
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    
    # Tracking
    tracking_id = Column(String(100), nullable=True, index=True)  # For open/click tracking
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Headers
    headers = Column(JSON, default=dict, nullable=False)
    
    # Attachments
    attachments = Column(JSON, default=list, nullable=False)  # List of attachment URLs
    
    # Error Handling
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_email_log_lead_status", "lead_id", "status"),
        Index("idx_email_log_provider_message", "provider_message_id"),
        Index("idx_email_log_tracking", "tracking_id"),
        Index("idx_email_log_sent_at", "sent_at"),
        Index("idx_email_log_status_created", "status", "created_at"),
    )
    
    def mark_queued(self):
        """Mark email as queued"""
        self.status = EmailStatus.QUEUED
        self.queued_at = datetime.utcnow()
    
    def mark_sent(self, provider_message_id: str = None):
        """Mark email as sent"""
        self.status = EmailStatus.SENT
        self.sent_at = datetime.utcnow()
        if provider_message_id:
            self.provider_message_id = provider_message_id
    
    def mark_delivered(self):
        """Mark email as delivered"""
        self.status = EmailStatus.DELIVERED
        self.delivered_at = datetime.utcnow()
    
    def mark_opened(self, ip_address: str = None, user_agent: str = None):
        """Mark email as opened"""
        self.status = EmailStatus.OPENED
        self.open_count += 1
        if not self.opened_at:
            self.opened_at = datetime.utcnow()
        if ip_address:
            self.ip_address = ip_address
        if user_agent:
            self.user_agent = user_agent
    
    def mark_clicked(self):
        """Mark email link as clicked"""
        self.status = EmailStatus.CLICKED
        self.click_count += 1
        if not self.first_clicked_at:
            self.first_clicked_at = datetime.utcnow()
    
    def mark_bounced(self, error: str = None):
        """Mark email as bounced"""
        self.status = EmailStatus.BOUNCED
        self.bounced_at = datetime.utcnow()
        if error:
            self.error_message = error
    
    def mark_failed(self, error: str = None, error_code: str = None):
        """Mark email as failed"""
        self.status = EmailStatus.FAILED
        if error:
            self.error_message = error
        if error_code:
            self.error_code = error_code
    
    def can_retry(self) -> bool:
        """Check if email can be retried"""
        return self.retry_count < self.max_retries and self.status in [
            EmailStatus.FAILED,
            EmailStatus.BOUNCED
        ]
    
    def increment_retry(self):
        """Increment retry counter and schedule next retry"""
        self.retry_count += 1
        # Exponential backoff: 5min, 15min, 45min
        delays = [300, 900, 2700]
        if self.retry_count <= len(delays):
            delay = delays[self.retry_count - 1]
            self.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
    
    def get_delivery_chain(self) -> dict:
        """Get complete delivery timeline"""
        return {
            "queued_at": self.queued_at.isoformat() if self.queued_at else None,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "clicked_at": self.first_clicked_at.isoformat() if self.first_clicked_at else None,
            "bounced_at": self.bounced_at.isoformat() if self.bounced_at else None
        }
    
    def __repr__(self):
        return f"<EmailLog {self.to_email} - {self.status.value}>"