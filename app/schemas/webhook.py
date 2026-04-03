"""
Webhook Pydantic Schemas
Request/Response validation for webhook endpoints
"""

from pydantic import BaseModel, Field, HttpUrl, ConfigDict, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID
from enum import Enum


class WebhookEventType(str, Enum):
    """Webhook event types"""
    CAMPAIGN_STARTED = "campaign.started"
    CAMPAIGN_COMPLETED = "campaign.completed"
    CAMPAIGN_FAILED = "campaign.failed"
    LEAD_CREATED = "lead.created"
    LEAD_UPDATED = "lead.updated"
    LEAD_QUALIFIED = "lead.qualified"
    LEAD_CONVERTED = "lead.converted"
    SCRAPING_JOB_STARTED = "scraping.job.started"
    SCRAPING_JOB_COMPLETED = "scraping.job.completed"
    SCRAPING_JOB_FAILED = "scraping.job.failed"


class WebhookStatus(str, Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


class WebhookCreate(BaseModel):
    """Schema for creating a webhook subscription"""
    url: HttpUrl = Field(..., description="Webhook endpoint URL")
    events: List[WebhookEventType] = Field(..., description="Events to subscribe to")
    secret: Optional[str] = Field(None, description="Secret for signing webhooks")
    description: Optional[str] = Field(None, max_length=500)
    is_active: bool = Field(default=True)
    
    @field_validator("events")
    @classmethod
    def validate_events(cls, v):
        if not v:
            raise ValueError("At least one event must be specified")
        if len(v) > 20:
            raise ValueError("Maximum 20 events per webhook")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://myapp.com/webhooks/leadgen",
                "events": ["lead.created", "lead.qualified", "campaign.completed"],
                "secret": "my-webhook-secret",
                "description": "Production webhook endpoint"
            }
        }
    )


class WebhookUpdate(BaseModel):
    """Schema for updating a webhook subscription"""
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventType]] = None
    secret: Optional[str] = None
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    """Schema for webhook subscription response"""
    id: UUID
    url: str
    events: List[str]
    secret: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class WebhookDeliveryResponse(BaseModel):
    """Schema for webhook delivery response"""
    id: UUID
    webhook_id: UUID
    event_type: str
    status: WebhookStatus
    response_status_code: Optional[int]
    retry_count: int
    delivered_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class WebhookPayload(BaseModel):
    """Standard webhook payload format"""
    id: str = Field(..., description="Unique webhook event ID")
    event: str = Field(..., description="Event type")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(..., description="Event data payload")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "evt_1234567890",
                "event": "lead.created",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {
                    "lead_id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "john@example.com",
                    "company": "Tech Corp"
                }
            }
        }
    )


class WebhookTestRequest(BaseModel):
    """Schema for testing webhook endpoint"""
    url: HttpUrl = Field(..., description="Webhook URL to test")
    event: WebhookEventType = Field(default=WebhookEventType.LEAD_CREATED)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "url": "https://myapp.com/webhooks/test",
                "event": "lead.created"
            }
        }
    )


class WebhookTestResponse(BaseModel):
    """Schema for webhook test response"""
    success: bool
    status_code: int
    response_body: Optional[str]
    duration_ms: int
    message: str


class WebhookDeliveryAttempt(BaseModel):
    """Schema for manual webhook retry"""
    delivery_id: UUID
    force_retry: bool = Field(default=False)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "delivery_id": "123e4567-e89b-12d3-a456-426614174000",
                "force_retry": True
            }
        }
    )