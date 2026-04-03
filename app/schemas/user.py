"""
User Pydantic Schemas
Request/Response validation for user management
"""

from pydantic import BaseModel, Field, EmailStr, ConfigDict, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


class UserRole(str, Enum):
    """User role enum for API"""
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"


class UserStatus(str, Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class UserCreate(BaseModel):
    """Schema for creating a new user"""
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=8, max_length=100, description="User password")
    full_name: Optional[str] = Field(None, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    role: UserRole = Field(default=UserRole.USER)
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123",
                "full_name": "John Doe",
                "company": "Tech Corp",
                "role": "user"
            }
        }
    )


class UserUpdate(BaseModel):
    """Schema for updating user information"""
    full_name: Optional[str] = Field(None, max_length=255)
    company: Optional[str] = Field(None, max_length=255)
    role: Optional[UserRole] = None
    email_notifications: Optional[bool] = None
    slack_webhook_url: Optional[str] = Field(None, max_length=500)
    default_export_format: Optional[str] = Field(None, pattern="^(csv|json|excel)$")


class UserPasswordUpdate(BaseModel):
    """Schema for password change"""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)
    
    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.islower() for c in v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        return v


class UserResponse(BaseModel):
    """Schema for user response (without sensitive data)"""
    id: UUID
    email: str
    full_name: Optional[str]
    company: Optional[str]
    role: UserRole
    status: UserStatus
    email_notifications: bool
    default_export_format: str
    monthly_lead_quota: int
    leads_generated_this_month: int
    created_at: datetime
    last_login_at: Optional[datetime]
    
    model_config = ConfigDict(from_attributes=True)


class UserQuotaResponse(BaseModel):
    """Schema for user quota information"""
    monthly_quota: int
    used_this_month: int
    remaining: int
    reset_at: Optional[datetime]
    percentage_used: float
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "monthly_quota": 1000,
                "used_this_month": 250,
                "remaining": 750,
                "reset_at": "2024-02-01T00:00:00Z",
                "percentage_used": 25.0
            }
        }
    )


class APIKeyCreate(BaseModel):
    """Schema for creating an API key"""
    name: str = Field(..., min_length=1, max_length=100, description="Key identifier")
    expires_in_days: Optional[int] = Field(default=365, ge=1, le=730, description="Expiry in days")
    permissions: List[str] = Field(default=["read"], description="Allowed permissions")
    allowed_ips: Optional[List[str]] = Field(None, description="Restrict to these IPs")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Production API Key",
                "expires_in_days": 365,
                "permissions": ["read", "write"],
                "allowed_ips": ["192.168.1.1", "10.0.0.1"]
            }
        }
    )


class APIKeyResponse(BaseModel):
    """Schema for API key response"""
    id: UUID
    name: str
    key_prefix: str
    permissions: List[str]
    allowed_ips: Optional[List[str]]
    expires_at: Optional[datetime]
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class APIKeyCreatedResponse(APIKeyResponse):
    """Schema for API key creation response (includes full key)"""
    key: str = Field(..., description="Full API key - store this securely")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Production API Key",
                "key": "leadgen_live_abc123def456ghi789",
                "key_prefix": "leadgen_live",
                "permissions": ["read", "write"],
                "expires_at": "2025-01-01T00:00:00Z",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z"
            }
        }
    )


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "SecurePass123"
            }
        }
    )


class UserLoginResponse(BaseModel):
    """Schema for login response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
                "expires_in": 1800,
                "user": {
                    "id": "123e4567...",
                    "email": "user@example.com",
                    "full_name": "John Doe"
                }
            }
        }
    )