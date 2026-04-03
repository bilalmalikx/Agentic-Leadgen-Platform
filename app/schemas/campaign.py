"""
Campaign Pydantic Schemas
Request/Response validation for campaign operations
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class CampaignStatusEnum(str, Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class CampaignPriorityEnum(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class CampaignSourceConfig(BaseModel):
    """Configuration for each source"""
    enabled: bool = True
    max_results: int = Field(default=100, ge=1, le=1000)
    search_type: Optional[str] = None
    additional_params: Dict[str, Any] = Field(default_factory=dict)


class CampaignCreate(BaseModel):
    """Schema for creating a new campaign"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    query: str = Field(..., min_length=1, description="Search query for leads")
    keywords: Optional[List[str]] = Field(None, description="Target keywords")
    locations: Optional[List[str]] = Field(None, description="Target locations")
    industries: Optional[List[str]] = Field(None, description="Target industries")
    job_titles: Optional[List[str]] = Field(None, description="Target job titles")
    sources: List[str] = Field(..., description="Sources to scrape")
    source_config: Optional[Dict[str, CampaignSourceConfig]] = Field(default_factory=dict)
    target_leads_count: int = Field(default=100, ge=1, le=10000)
    max_leads_per_source: int = Field(default=50, ge=1, le=5000)
    min_score_threshold: int = Field(default=0, ge=0, le=100)
    enable_deduplication: bool = True
    enable_enrichment: bool = True
    enable_scoring: bool = True
    scheduled_start_at: Optional[datetime] = None
    priority: CampaignPriorityEnum = CampaignPriorityEnum.MEDIUM
    webhook_url: Optional[str] = None
    webhook_events: Optional[List[str]] = Field(None, description="Events to trigger webhook")
    auto_export: bool = False
    export_format: str = Field(default="csv", pattern="^(csv|json|excel)$")
    export_destination: Optional[str] = None
    
    @field_validator("sources")
    @classmethod
    def validate_sources(cls, v):
        valid_sources = ["linkedin", "twitter", "crunchbase", "company_website"]
        for source in v:
            if source not in valid_sources:
                raise ValueError(f"Invalid source: {source}. Must be one of {valid_sources}")
        return v
    
    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v):
        if v and not (v.startswith("http://") or v.startswith("https://")):
            raise ValueError("Webhook URL must start with http:// or https://")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "AI SaaS Founders Campaign",
                "query": "founder of AI startup",
                "sources": ["linkedin", "twitter"],
                "target_leads_count": 500,
                "priority": "high"
            }
        }
    )


class CampaignUpdate(BaseModel):
    """Schema for updating an existing campaign"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    query: Optional[str] = Field(None, min_length=1)
    keywords: Optional[List[str]] = None
    locations: Optional[List[str]] = None
    industries: Optional[List[str]] = None
    job_titles: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    target_leads_count: Optional[int] = Field(None, ge=1, le=10000)
    min_score_threshold: Optional[int] = Field(None, ge=0, le=100)
    priority: Optional[CampaignPriorityEnum] = None
    status: Optional[CampaignStatusEnum] = None
    scheduled_start_at: Optional[datetime] = None
    webhook_url: Optional[str] = None


class CampaignResponse(BaseModel):
    """Schema for campaign response"""
    id: UUID
    name: str
    description: Optional[str]
    query: str
    keywords: Optional[List[str]]
    locations: Optional[List[str]]
    industries: Optional[List[str]]
    job_titles: Optional[List[str]]
    sources: List[str]
    source_config: Dict[str, Any]
    target_leads_count: int
    max_leads_per_source: int
    min_score_threshold: int
    enable_deduplication: bool
    enable_enrichment: bool
    enable_scoring: bool
    status: CampaignStatusEnum
    priority: CampaignPriorityEnum
    progress_percentage: int
    total_leads_found: int
    unique_leads_added: int
    duplicate_leads_skipped: int
    failed_scrapes: int
    scheduled_start_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    webhook_url: Optional[str]
    webhook_events: Optional[List[str]]
    auto_export: bool
    export_format: str
    export_destination: Optional[str]
    created_by: Optional[UUID]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class CampaignDetailResponse(CampaignResponse):
    """Detailed campaign response with additional info"""
    leads_preview: List[Dict[str, Any]] = Field(default=[], description="First 10 leads")
    scraping_jobs: List[Dict[str, Any]] = Field(default=[], description="Scraping job summaries")
    
    model_config = ConfigDict(from_attributes=True)


class CampaignStatsResponse(BaseModel):
    """Campaign statistics response"""
    campaign_id: UUID
    total_leads: int
    qualified_leads: int
    contacted_leads: int
    converted_leads: int
    rejected_leads: int
    duplicate_leads: int
    average_score: float
    leads_by_source: Dict[str, int]
    leads_by_quality: Dict[str, int]
    leads_by_day: List[Dict[str, Any]]
    top_companies: List[Dict[str, Any]]
    top_job_titles: List[Dict[str, Any]]
    
    model_config = ConfigDict(from_attributes=True)


class CampaignStartRequest(BaseModel):
    """Request to start a campaign"""
    start_now: bool = Field(default=True, description="Start immediately")
    scheduled_start_at: Optional[datetime] = Field(None, description="Schedule for later")
    notify_on_complete: bool = Field(default=True)
    notify_email: Optional[str] = None


class CampaignDuplicateRequest(BaseModel):
    """Request to duplicate a campaign"""
    new_name: str = Field(..., min_length=1, max_length=255)
    copy_leads: bool = Field(default=False, description="Copy existing leads")
    adjust_dates: bool = Field(default=True, description="Adjust schedule dates")