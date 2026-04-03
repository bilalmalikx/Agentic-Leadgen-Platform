"""
Analytics Pydantic Schemas
Request/Response validation for analytics and reporting endpoints
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID
from enum import Enum


class TimeGranularity(str, Enum):
    """Time granularity for analytics"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"


class AnalyticsFilter(BaseModel):
    """Filters for analytics queries"""
    campaign_id: Optional[UUID] = None
    source: Optional[str] = None
    status: Optional[str] = None
    quality: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    granularity: TimeGranularity = Field(default=TimeGranularity.DAY)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000",
                "source": "linkedin",
                "start_date": "2024-01-01T00:00:00Z",
                "end_date": "2024-01-31T23:59:59Z",
                "granularity": "day"
            }
        }
    )


class LeadGenerationStats(BaseModel):
    """Lead generation statistics"""
    total_leads: int
    new_leads_today: int
    new_leads_this_week: int
    new_leads_this_month: int
    average_daily_leads: float
    leads_by_source: Dict[str, int]
    leads_by_status: Dict[str, int]
    leads_by_quality: Dict[str, int]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_leads": 5000,
                "new_leads_today": 150,
                "new_leads_this_week": 850,
                "new_leads_this_month": 3200,
                "average_daily_leads": 106.67,
                "leads_by_source": {"linkedin": 2500, "twitter": 1500, "crunchbase": 1000},
                "leads_by_status": {"new": 2000, "qualified": 1500, "converted": 500},
                "leads_by_quality": {"hot": 800, "warm": 2000, "cold": 2200}
            }
        }
    )


class ScoreDistribution(BaseModel):
    """Lead score distribution"""
    score_range: str
    count: int
    percentage: float
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "score_range": "80-100",
                "count": 800,
                "percentage": 16.0
            }
        }
    )


class TimeSeriesDataPoint(BaseModel):
    """Time series data point"""
    timestamp: str
    value: int
    metadata: Optional[Dict[str, Any]] = None


class TimeSeriesResponse(BaseModel):
    """Time series analytics response"""
    metric: str
    granularity: str
    data: List[TimeSeriesDataPoint]
    total: int
    average: float
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "metric": "leads_created",
                "granularity": "day",
                "data": [
                    {"timestamp": "2024-01-01", "value": 100},
                    {"timestamp": "2024-01-02", "value": 150}
                ],
                "total": 250,
                "average": 125.0
            }
        }
    )


class ConversionFunnel(BaseModel):
    """Conversion funnel analytics"""
    stage: str
    count: int
    conversion_rate_from_previous: float
    conversion_rate_from_start: float
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "stage": "lead_created",
                "count": 5000,
                "conversion_rate_from_previous": 100.0,
                "conversion_rate_from_start": 100.0
            }
        }
    )


class CampaignPerformanceResponse(BaseModel):
    """Campaign performance analytics"""
    campaign_id: UUID
    campaign_name: str
    total_leads: int
    unique_leads: int
    qualified_leads: int
    converted_leads: int
    conversion_rate: float
    average_score: float
    cost_per_lead: Optional[float]
    roi_percentage: Optional[float]
    duration_hours: float
    leads_per_hour: float
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "campaign_id": "123e4567-e89b-12d3-a456-426614174000",
                "campaign_name": "AI SaaS Founders",
                "total_leads": 1000,
                "unique_leads": 950,
                "qualified_leads": 600,
                "converted_leads": 120,
                "conversion_rate": 12.0,
                "average_score": 72.5,
                "duration_hours": 2.5,
                "leads_per_hour": 380.0
            }
        }
    )


class DashboardSummary(BaseModel):
    """Dashboard summary statistics"""
    total_campaigns: int
    active_campaigns: int
    total_leads: int
    qualified_leads: int
    converted_leads: int
    average_lead_score: float
    leads_today: int
    leads_this_week: int
    leads_this_month: int
    top_performing_campaign: Optional[CampaignPerformanceResponse]
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_campaigns": 15,
                "active_campaigns": 3,
                "total_leads": 5000,
                "qualified_leads": 1500,
                "converted_leads": 300,
                "average_lead_score": 65.5,
                "leads_today": 150,
                "leads_this_week": 850,
                "leads_this_month": 3200
            }
        }
    )


class ExportAnalyticsRequest(BaseModel):
    """Request to export analytics data"""
    report_type: str = Field(..., pattern="^(leads|campaigns|conversion|score_distribution)$")
    format: str = Field(default="csv", pattern="^(csv|json|excel)$")
    filters: AnalyticsFilter
    include_charts: bool = Field(default=False)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_type": "leads",
                "format": "csv",
                "filters": {
                    "start_date": "2024-01-01T00:00:00Z",
                    "end_date": "2024-01-31T23:59:59Z"
                },
                "include_charts": False
            }
        }
    )


class RealTimeMetrics(BaseModel):
    """Real-time system metrics"""
    leads_per_minute: float
    active_campaigns: int
    queue_size: int
    active_workers: int
    api_requests_per_minute: float
    average_response_time_ms: float
    error_rate_percentage: float
    timestamp: datetime
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "leads_per_minute": 12.5,
                "active_campaigns": 3,
                "queue_size": 45,
                "active_workers": 8,
                "api_requests_per_minute": 234.0,
                "average_response_time_ms": 156.0,
                "error_rate_percentage": 0.5,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        }
    )