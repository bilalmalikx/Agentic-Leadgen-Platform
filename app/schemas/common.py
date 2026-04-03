"""
Common Pydantic Schemas
Reusable schemas across the application
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Generic, TypeVar, List, Any
from datetime import datetime
from uuid import UUID

# Generic type for paginated responses
T = TypeVar('T')


class HealthResponse(BaseModel):
    """Health check response schema"""
    status: str = Field(..., description="Overall health status")
    timestamp: str = Field(..., description="Current timestamp")
    app: str = Field(..., description="Application name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Environment (dev/staging/prod)")
    services: dict = Field(..., description="Individual service health status")


class ErrorResponse(BaseModel):
    """Standard error response schema"""
    success: bool = Field(default=False)
    error_code: str = Field(..., description="Error code for client handling")
    message: str = Field(..., description="Human readable error message")
    details: Optional[Any] = Field(default=None, description="Additional error details")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracing")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Rate limit exceeded. Try again in 60 seconds.",
                "request_id": "req_abc123",
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
    )


class SuccessResponse(BaseModel):
    """Standard success response schema"""
    success: bool = Field(default=True)
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(default=None, description="Response data")
    request_id: Optional[str] = Field(default=None, description="Request ID for tracing")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {"id": "123"},
                "timestamp": "2024-01-01T00:00:00Z"
            }
        }
    )


class PaginationParams(BaseModel):
    """Pagination query parameters"""
    page: int = Field(default=1, ge=1, description="Page number (starts at 1)")
    limit: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")
    sort_by: Optional[str] = Field(default=None, description="Sort field")
    sort_order: str = Field(default="desc", pattern="^(asc|desc)$", description="Sort order")
    
    def offset(self) -> int:
        """Calculate SQL OFFSET"""
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response schema"""
    items: List[T] = Field(..., description="List of items for current page")
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    limit: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(..., description="Whether next page exists")
    has_prev: bool = Field(..., description="Whether previous page exists")
    
    @classmethod
    def create(cls, items: List[T], total: int, params: PaginationParams):
        """Create paginated response from query results"""
        total_pages = (total + params.limit - 1) // params.limit
        
        return cls(
            items=items,
            total=total,
            page=params.page,
            limit=params.limit,
            total_pages=total_pages,
            has_next=params.page < total_pages,
            has_prev=params.page > 1
        )


class DateRangeFilter(BaseModel):
    """Date range filter for queries"""
    start_date: Optional[datetime] = Field(default=None, description="Start date (inclusive)")
    end_date: Optional[datetime] = Field(default=None, description="End date (inclusive)")
    
    def to_filter(self) -> dict:
        """Convert to dictionary filter"""
        filter_dict = {}
        if self.start_date:
            filter_dict["gte"] = self.start_date
        if self.end_date:
            filter_dict["lte"] = self.end_date
        return filter_dict


class IDResponse(BaseModel):
    """Response containing just an ID"""
    id: UUID = Field(..., description="Resource ID")
    message: str = Field(default="Resource created successfully")


class BulkOperationResponse(BaseModel):
    """Response for bulk operations"""
    total: int = Field(..., description="Total items processed")
    successful: int = Field(..., description="Successfully processed items")
    failed: int = Field(..., description="Failed items")
    errors: List[dict] = Field(default=[], description="List of errors for failed items")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 100,
                "successful": 95,
                "failed": 5,
                "errors": [
                    {"index": 10, "reason": "Invalid email format"}
                ]
            }
        }
    )


class WebhookPayload(BaseModel):
    """Standard webhook payload schema"""
    event_type: str = Field(..., description="Type of event")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: dict = Field(..., description="Event data payload")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "event_type": "lead.created",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {
                    "lead_id": "123",
                    "email": "john@example.com"
                }
            }
        }
    )