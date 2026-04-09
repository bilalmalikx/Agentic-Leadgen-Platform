"""
Scraping Job Model - Tracks individual scraping jobs
"""

from datetime import datetime
from sqlalchemy import Column, String, Integer, JSON, Enum, Text, ForeignKey, Index, Float, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel, AuditMixin


class JobStatus(enum.Enum):
    """Scraping job status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    CANCELLED = "cancelled"


class SourceType(enum.Enum):
    """Source being scraped"""
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    CRUNCHBASE = "crunchbase"
    COMPANY_WEBSITE = "company_website"
    GOOGLE_SEARCH = "google_search"
    CUSTOM_API = "custom_api"


class ScrapingJob(BaseModel, AuditMixin):
    """Scraping Job model - tracks each scraping run"""
    
    __tablename__ = "scraping_jobs"
    
    # Basic Information
    job_name = Column(String(255), nullable=True)
    source = Column(Enum(SourceType), nullable=False, index=True)
    
    # Campaign Association
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)
    campaign = relationship("Campaign", back_populates="scraping_jobs")
    
    # Leads Association
    leads = relationship("Lead", back_populates="scraping_job")
    
    # Search Parameters
    search_query = Column(Text, nullable=False)
    search_params = Column(JSON, default=dict, nullable=False)
    
    # Pagination/Cursor
    cursor = Column(String(500), nullable=True)
    page = Column(Integer, default=1)
    limit = Column(Integer, default=100)
    
    # Status & Progress
    status = Column(Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True)
    progress_percentage = Column(Integer, default=0, nullable=False)
    
    # Counts
    total_items_found = Column(Integer, default=0, nullable=False)
    items_scraped = Column(Integer, default=0, nullable=False)
    items_failed = Column(Integer, default=0, nullable=False)
    items_duplicate = Column(Integer, default=0, nullable=False)
    
    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    estimated_duration_seconds = Column(Integer, nullable=True)
    
    # Performance Metrics
    avg_response_time_ms = Column(Float, nullable=True)
    requests_per_second = Column(Float, nullable=True)
    
    # Error Handling
    error_message = Column(Text, nullable=True)
    error_stack = Column(Text, nullable=True)
    failed_items = Column(JSON, default=list, nullable=False)
    
    # Proxy Information
    proxy_used = Column(String(255), nullable=True)
    proxy_rotated_count = Column(Integer, default=0)
    
    # Retry Information
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Rate Limiting
    rate_limit_hit = Column(Boolean, default=False)
    rate_limit_reset_at = Column(DateTime(timezone=True), nullable=True)
    
    # Raw Response (for debugging)
    raw_response_sample = Column(Text, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_scraping_job_campaign_status", "campaign_id", "status"),
        Index("idx_scraping_job_source_status", "source", "status"),
        Index("idx_scraping_job_created", "created_at"),
    )
    
    def mark_started(self):
        """Mark job as started"""
        self.status = JobStatus.RUNNING
        self.started_at = datetime.utcnow()
    
    def mark_completed(self):
        """Mark job as completed"""
        self.status = JobStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        
        if self.started_at:
            duration = (self.completed_at - self.started_at).total_seconds()
            self.estimated_duration_seconds = int(duration)
    
    def mark_failed(self, error: str, stack_trace: str = None):
        """Mark job as failed"""
        self.status = JobStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error
        self.error_stack = stack_trace
    
    def mark_partial(self):
        """Mark job as partially completed"""
        self.status = JobStatus.PARTIAL
        self.completed_at = datetime.utcnow()
    
    def update_progress(self, scraped: int, total: int = None):
        """Update progress percentage"""
        self.items_scraped = scraped
        if total:
            self.total_items_found = total
            self.progress_percentage = int((scraped / total) * 100) if total > 0 else 0
    
    def increment_failed(self, count: int = 1):
        """Increment failed items count"""
        self.items_failed += count
    
    def increment_duplicate(self, count: int = 1):
        """Increment duplicate items count"""
        self.items_duplicate += count
    
    def add_failed_item(self, item_data: dict):
        """Add failed item to list"""
        self.failed_items.append(item_data)
        if len(self.failed_items) > 100:
            self.failed_items = self.failed_items[-100:]
    
    def record_rate_limit_hit(self, reset_at: datetime = None):
        """Record rate limit hit"""
        self.rate_limit_hit = True
        self.rate_limit_reset_at = reset_at
    
    def can_retry(self) -> bool:
        """Check if job can be retried"""
        return self.retry_count < self.max_retries
    
    def increment_retry(self):
        """Increment retry counter"""
        self.retry_count += 1
    
    def get_summary(self) -> dict:
        """Get job summary"""
        return {
            "id": str(self.id),
            "source": self.source.value if self.source else None,
            "status": self.status.value if self.status else None,
            "progress": self.progress_percentage,
            "scraped": self.items_scraped,
            "total": self.total_items_found,
            "failed": self.items_failed,
            "duplicates": self.items_duplicate,
            "duration_seconds": self.estimated_duration_seconds,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }
    
    def __repr__(self):
        return f"<ScrapingJob {self.source.value} - {self.status.value}>"