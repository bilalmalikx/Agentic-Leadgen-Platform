"""
Lead Model - Stores all generated leads
Main entity of the system
"""

from sqlalchemy import Column, String, Integer, Float, JSON, Enum, Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin


class LeadStatus(enum.Enum):
    """Lead status enum"""
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class LeadSource(enum.Enum):
    """Source of lead"""
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    CRUNCHBASE = "crunchbase"
    COMPANY_WEBSITE = "company_website"
    MANUAL = "manual"
    API = "api"


class LeadQuality(enum.Enum):
    """Lead quality score category"""
    HOT = "hot"      # 80-100
    WARM = "warm"    # 60-79
    COLD = "cold"    # 40-59
    UNQUALIFIED = "unqualified"  # <40


class Lead(BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin):
    """Lead model - stores prospect information"""
    
    __tablename__ = "leads"
    
    # Basic Information
    email = Column(String(255), nullable=False, unique=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    full_name = Column(String(200), nullable=True)
    
    # Professional Information
    company_name = Column(String(255), nullable=True, index=True)
    company_website = Column(String(500), nullable=True)
    job_title = Column(String(255), nullable=True)
    industry = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    country = Column(String(100), nullable=True)
    
    # Contact Information
    phone = Column(String(50), nullable=True)
    linkedin_url = Column(String(500), nullable=True, index=True)
    twitter_handle = Column(String(100), nullable=True)
    
    # Scoring & Qualification
    score = Column(Integer, default=0, nullable=False)  # 0-100
    quality = Column(Enum(LeadQuality), default=LeadQuality.UNQUALIFIED, nullable=False)
    status = Column(Enum(LeadStatus), default=LeadStatus.NEW, nullable=False, index=True)
    source = Column(Enum(LeadSource), nullable=False)
    
    # Enriched Data (from AI)
    enriched_data = Column(JSON, default=dict, nullable=False)
    company_size = Column(String(50), nullable=True)  # 1-10, 11-50, 51-200, 201-500, 501-1000, 1000+
    funding_stage = Column(String(50), nullable=True)  # Seed, Series A, Series B, etc.
    tech_stack = Column(ARRAY(String), nullable=True)  # List of technologies used
    
    # Engagement Metrics
    email_opened_count = Column(Integer, default=0)
    email_clicked_count = Column(Integer, default=0)
    website_visits = Column(Integer, default=0)
    
    # Scraping Metadata
    raw_scraped_data = Column(JSON, default=dict, nullable=False)  # Original scraped data
    scraping_job_id = Column(UUID(as_uuid=True), ForeignKey("scraping_jobs.id"), nullable=True)
    
    # Campaign Association
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaigns.id"), nullable=False, index=True)
    
    # Vector Embedding ID (for ChromaDB)
    vector_id = Column(String(100), nullable=True, index=True)
    
    # Relationships
    campaign = relationship("Campaign", back_populates="leads")
    scraping_job = relationship("ScrapingJob", back_populates="leads")
    email_logs = relationship("EmailLog", back_populates="lead", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_lead_score_status", "score", "status"),
        Index("idx_lead_company_quality", "company_name", "quality"),
        Index("idx_lead_created_source", "created_at", "source"),
        Index("idx_lead_campaign_status", "campaign_id", "status"),
    )
    
    def calculate_quality(self):
        """Calculate quality category based on score"""
        if self.score >= 80:
            self.quality = LeadQuality.HOT
        elif self.score >= 60:
            self.quality = LeadQuality.WARM
        elif self.score >= 40:
            self.quality = LeadQuality.COLD
        else:
            self.quality = LeadQuality.UNQUALIFIED
    
    def get_display_name(self) -> str:
        """Get full name or fallback to email"""
        if self.full_name:
            return self.full_name
        elif self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.email.split("@")[0]
    
    def to_search_dict(self) -> dict:
        """Convert to dictionary for search indexing"""
        return {
            "id": str(self.id),
            "full_name": self.full_name,
            "email": self.email,
            "company_name": self.company_name,
            "job_title": self.job_title,
            "location": self.location,
            "industry": self.industry,
            "score": self.score,
            "status": self.status.value if self.status else None,
            "quality": self.quality.value if self.quality else None,
        }
    
    def __repr__(self):
        return f"<Lead {self.email} - Score: {self.score}>"