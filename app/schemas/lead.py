"""
Lead Pydantic Schemas
Request/Response validation for lead operations
"""

from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from enum import Enum

from app.models.lead import LeadStatus, LeadSource, LeadQuality


class LeadStatusEnum(str, Enum):
    """Lead status for API responses"""
    NEW = "new"
    CONTACTED = "contacted"
    QUALIFIED = "qualified"
    CONVERTED = "converted"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class LeadSourceEnum(str, Enum):
    """Lead source for API"""
    LINKEDIN = "linkedin"
    TWITTER = "twitter"
    CRUNCHBASE = "crunchbase"
    COMPANY_WEBSITE = "company_website"
    MANUAL = "manual"
    API = "api"


class LeadQualityEnum(str, Enum):
    """Lead quality categories"""
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    UNQUALIFIED = "unqualified"


class LeadCreate(BaseModel):
    """Schema for creating a new lead"""
    email: EmailStr = Field(..., description="Lead email address")
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=255)
    company_website: Optional[str] = Field(None, max_length=500)
    job_title: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    linkedin_url: Optional[str] = Field(None, max_length=500)
    twitter_handle: Optional[str] = Field(None, max_length=100)
    source: LeadSourceEnum = Field(..., description="Source of lead")
    campaign_id: UUID = Field(..., description="Associated campaign ID")
    
    @field_validator("linkedin_url")
    @classmethod
    def validate_linkedin_url(cls, v):
        """Validate LinkedIn URL format"""
        if v and "linkedin.com" not in v:
            raise ValueError("Invalid LinkedIn URL")
        return v
    
    @field_validator("company_website")
    @classmethod
    def validate_website(cls, v):
        """Validate website URL format"""
        if v and not (v.startswith("http://") or v.startswith("https://")):
            v = f"https://{v}"
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "company_name": "Tech Corp",
                "job_title": "CTO",
                "source": "linkedin",
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }
    )


class LeadUpdate(BaseModel):
    """Schema for updating an existing lead"""
    first_name: Optional[str] = Field(None, max_length=100)
    last_name: Optional[str] = Field(None, max_length=100)
    company_name: Optional[str] = Field(None, max_length=255)
    job_title: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    status: Optional[LeadStatusEnum] = None
    score: Optional[int] = Field(None, ge=0, le=100)
    notes: Optional[str] = None


class LeadResponse(BaseModel):
    """Schema for lead response"""
    id: UUID
    email: str
    first_name: Optional[str]
    last_name: Optional[str]
    full_name: Optional[str]
    company_name: Optional[str]
    company_website: Optional[str]
    job_title: Optional[str]
    industry: Optional[str]
    location: Optional[str]
    country: Optional[str]
    phone: Optional[str]
    linkedin_url: Optional[str]
    twitter_handle: Optional[str]
    score: int
    quality: LeadQualityEnum
    status: LeadStatusEnum
    source: LeadSourceEnum
    enriched_data: Dict[str, Any]
    company_size: Optional[str]
    funding_stage: Optional[str]
    tech_stack: Optional[List[str]]
    email_opened_count: int
    email_clicked_count: int
    campaign_id: UUID
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class LeadDetailResponse(LeadResponse):
    """Detailed lead response with additional metadata"""
    raw_scraped_data: Dict[str, Any]
    scraping_job_id: Optional[UUID]
    vector_id: Optional[str]
    metadata: Dict[str, Any]


class LeadSearchParams(BaseModel):
    """Parameters for searching leads"""
    query: Optional[str] = Field(None, description="Full-text search query")
    email: Optional[str] = Field(None, description="Filter by email")
    company_name: Optional[str] = Field(None, description="Filter by company")
    status: Optional[LeadStatusEnum] = None
    source: Optional[LeadSourceEnum] = None
    quality: Optional[LeadQualityEnum] = None
    min_score: Optional[int] = Field(None, ge=0, le=100)
    max_score: Optional[int] = Field(None, ge=0, le=100)
    campaign_id: Optional[UUID] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    has_email_opened: Optional[bool] = None
    has_phone: Optional[bool] = None
    has_linkedin: Optional[bool] = None


class LeadBulkCreate(BaseModel):
    """Schema for bulk lead creation"""
    leads: List[LeadCreate] = Field(..., max_length=1000, description="List of leads to create")
    
    @field_validator("leads")
    @classmethod
    def validate_bulk_limit(cls, v):
        if len(v) > 1000:
            raise ValueError("Maximum 1000 leads per bulk operation")
        return v


class LeadExportRequest(BaseModel):
    """Schema for lead export request"""
    format: str = Field(default="csv", pattern="^(csv|json|excel)$", description="Export format")
    filters: Optional[LeadSearchParams] = None
    fields: Optional[List[str]] = Field(None, description="Specific fields to export")
    include_metadata: bool = Field(default=False)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "format": "csv",
                "filters": {"status": "qualified", "min_score": 80},
                "fields": ["email", "company_name", "score"],
                "include_metadata": False
            }
        }
    )


class LeadScoreUpdate(BaseModel):
    """Schema for updating lead scores"""
    lead_ids: List[UUID] = Field(..., max_length=100)
    recalculate: bool = Field(default=True, description="Recalculate scores using algorithm")
    manual_scores: Optional[Dict[UUID, int]] = Field(None, description="Manual score overrides")


class LeadQualifyRequest(BaseModel):
    """Schema for lead qualification request"""
    lead_ids: List[UUID] = Field(..., max_length=100)
    use_ai: bool = Field(default=True, description="Use AI for qualification")
    threshold: int = Field(default=60, ge=0, le=100, description="Minimum score to qualify")