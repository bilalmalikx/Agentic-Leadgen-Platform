"""
Campaign Model - Stores lead generation campaigns
Each campaign defines what leads to scrape and from where
"""

from sqlalchemy import Column, String, Integer, JSON, Enum, Text, ForeignKey, Index, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel, AuditMixin, MetadataMixin


class CampaignStatus(enum.Enum):
    """Campaign status enum"""
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class CampaignPriority(enum.Enum):
    """Campaign priority"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class Campaign(BaseModel, AuditMixin, MetadataMixin):
    """Campaign model - defines lead generation parameters"""
    
    __tablename__ = "campaigns"
    
    # Basic Information
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    
    # Search Parameters
    query = Column(Text, nullable=False)  # Search query (e.g., "AI startup founders")
    keywords = Column(ARRAY(String), nullable=True)  # List of keywords
    locations = Column(ARRAY(String), nullable=True)  # Target locations
    industries = Column(ARRAY(String), nullable=True)  # Target industries
    job_titles = Column(ARRAY(String), nullable=True)  # Target job titles
    
    # Sources Configuration
    sources = Column(ARRAY(String), nullable=False)  # linkedin, twitter, crunchbase, etc.
    source_config = Column(JSON, default=dict, nullable=False)  # Source-specific config
    
    # Target Settings
    target_leads_count = Column(Integer, default=100, nullable=False)
    max_leads_per_source = Column(Integer, default=50, nullable=False)
    
    # Filters
    min_score_threshold = Column(Integer, default=0, nullable=False)  # Only keep leads with score >= this
    enable_deduplication = Column(Boolean, default=True, nullable=False)
    enable_enrichment = Column(Boolean, default=True, nullable=False)
    enable_scoring = Column(Boolean, default=True, nullable=False)
    
    # Schedule
    scheduled_start_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_end_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status & Progress
    status = Column(Enum(CampaignStatus), default=CampaignStatus.DRAFT, nullable=False, index=True)
    priority = Column(Enum(CampaignPriority), default=CampaignPriority.MEDIUM, nullable=False)
    progress_percentage = Column(Integer, default=0, nullable=False)  # 0-100
    
    # Counts
    total_leads_found = Column(Integer, default=0, nullable=False)
    unique_leads_added = Column(Integer, default=0, nullable=False)
    duplicate_leads_skipped = Column(Integer, default=0, nullable=False)
    failed_scrapes = Column(Integer, default=0, nullable=False)
    
    # Execution Details
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Webhook Configuration
    webhook_url = Column(String(500), nullable=True)
    webhook_events = Column(ARRAY(String), nullable=True)  # on_complete, on_lead_added, etc.
    
    # Export Configuration
    auto_export = Column(Boolean, default=False)
    export_format = Column(String(20), default="csv")  # csv, json, excel
    export_destination = Column(String(500), nullable=True)  # S3 path, email, etc.
    
    # Relationships
    leads = relationship("Lead", back_populates="campaign", cascade="all, delete-orphan")
    scraping_jobs = relationship("ScrapingJob", back_populates="campaign", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("idx_campaign_status_priority", "status", "priority"),
        Index("idx_campaign_scheduled_start", "scheduled_start_at"),
        Index("idx_campaign_user_created", "created_by"),
        Index("idx_campaign_status_created", "status", "created_at"),
    )
    
    def is_running(self) -> bool:
        """Check if campaign is currently running"""
        return self.status == CampaignStatus.RUNNING
    
    def is_completed(self) -> bool:
        """Check if campaign is completed"""
        return self.status == CampaignStatus.COMPLETED
    
    def get_progress(self) -> dict:
        """Get detailed progress information"""
        return {
            "percentage": self.progress_percentage,
            "total_found": self.total_leads_found,
            "unique_added": self.unique_leads_added,
            "duplicates": self.duplicate_leads_skipped,
            "failed": self.failed_scrapes,
            "target": self.target_leads_count
        }
    
    def mark_started(self):
        """Mark campaign as started"""
        self.status = CampaignStatus.RUNNING
        self.started_at = datetime.utcnow()
        self.last_run_at = datetime.utcnow()
    
    def mark_completed(self):
        """Mark campaign as completed"""
        self.status = CampaignStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.progress_percentage = 100
    
    def mark_failed(self, error: str):
        """Mark campaign as failed"""
        self.status = CampaignStatus.FAILED
        self.error_message = error
        self.completed_at = datetime.utcnow()
    
    def update_progress(self):
        """Update progress percentage based on leads found vs target"""
        if self.target_leads_count > 0:
            self.progress_percentage = min(100, int(
                (self.unique_leads_added / self.target_leads_count) * 100
            ))
    
    def __repr__(self):
        return f"<Campaign {self.name} - {self.status.value}>"