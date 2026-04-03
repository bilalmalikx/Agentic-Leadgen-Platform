"""
User Model - Authentication and API key management
"""

from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON, Text, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models.base import BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin


class UserRole(enum.Enum):
    """User role enum"""
    ADMIN = "admin"
    MANAGER = "manager"
    USER = "user"
    VIEWER = "viewer"


class UserStatus(enum.Enum):
    """User account status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class User(BaseModel, SoftDeleteMixin, AuditMixin, MetadataMixin):
    """User model - authentication and authorization"""
    
    __tablename__ = "users"
    
    # Basic Information
    email = Column(String(255), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    
    # Role & Permissions
    role = Column(Enum(UserRole), default=UserRole.USER, nullable=False)
    status = Column(Enum(UserStatus), default=UserStatus.ACTIVE, nullable=False, index=True)
    
    # API Keys (multiple keys per user)
    api_keys = relationship("APIKey", back_populates="user", cascade="all, delete-orphan")
    
    # Rate Limiting per user
    rate_limit_per_minute = Column(Integer, default=100, nullable=False)
    rate_limit_per_day = Column(Integer, default=10000, nullable=False)
    
    # Quota & Usage
    monthly_lead_quota = Column(Integer, default=1000, nullable=False)
    leads_generated_this_month = Column(Integer, default=0, nullable=False)
    api_calls_this_month = Column(Integer, default=0, nullable=False)
    quota_reset_at = Column(DateTime(timezone=True), nullable=True)
    
    # Preferences
    email_notifications = Column(Boolean, default=True)
    slack_webhook_url = Column(String(500), nullable=True)
    default_export_format = Column(String(20), default="csv")
    
    # Billing (if applicable)
    subscription_tier = Column(String(50), default="free")
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Last activity
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    last_ip = Column(String(45), nullable=True)
    
    # Relationships
    campaigns = relationship("Campaign", back_populates="user")
    
    # Indexes
    __table_args__ = (
        Index("idx_user_status_role", "status", "role"),
        Index("idx_user_email_status", "email", "status"),
    )
    
    def has_permission(self, required_role: UserRole) -> bool:
        """Check if user has required role permission"""
        role_priority = {
            UserRole.VIEWER: 1,
            UserRole.USER: 2,
            UserRole.MANAGER: 3,
            UserRole.ADMIN: 4
        }
        return role_priority[self.role] >= role_priority[required_role]
    
    def check_quota(self, leads_count: int = 1) -> bool:
        """Check if user has enough quota for more leads"""
        return (self.leads_generated_this_month + leads_count) <= self.monthly_lead_quota
    
    def consume_quota(self, leads_count: int = 1):
        """Consume user quota"""
        self.leads_generated_this_month += leads_count
    
    def reset_monthly_quota(self):
        """Reset monthly quota"""
        self.leads_generated_this_month = 0
        self.api_calls_this_month = 0
        self.quota_reset_at = datetime.utcnow()
    
    def update_last_login(self, ip_address: str = None):
        """Update last login timestamp"""
        self.last_login_at = datetime.utcnow()
        if ip_address:
            self.last_ip = ip_address
    
    def get_usage_stats(self) -> dict:
        """Get user usage statistics"""
        return {
            "leads_used": self.leads_generated_this_month,
            "leads_quota": self.monthly_lead_quota,
            "leads_remaining": self.monthly_lead_quota - self.leads_generated_this_month,
            "api_calls": self.api_calls_this_month,
            "quota_reset_at": self.quota_reset_at.isoformat() if self.quota_reset_at else None
        }
    
    def __repr__(self):
        return f"<User {self.email} - {self.role.value}>"


class APIKey(BaseModel, AuditMixin):
    """API Key model for programmatic access"""
    
    __tablename__ = "api_keys"
    
    # Key information
    key_hash = Column(String(255), nullable=False, unique=True, index=True)
    key_prefix = Column(String(10), nullable=False)  # First few chars for identification
    name = Column(String(255), nullable=False)  # Human-readable name
    
    # Association
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User", back_populates="api_keys")
    
    # Permissions
    permissions = Column(JSON, default=list, nullable=False)  # List of allowed endpoints
    allowed_ips = Column(ARRAY(String), nullable=True)  # Restrict to specific IPs
    
    # Expiration
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_apikey_user_active", "user_id", "is_active"),
        Index("idx_apikey_expires", "expires_at"),
    )
    
    def is_valid(self) -> bool:
        """Check if API key is still valid"""
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True
    
    def record_usage(self):
        """Record API key usage"""
        self.last_used_at = datetime.utcnow()
    
    def __repr__(self):
        return f"<APIKey {self.key_prefix}... - User: {self.user_id}>"