"""
Audit Log Model
Tracks all important actions for compliance and debugging
"""

from sqlalchemy import Column, String, Integer, JSON, Text, ForeignKey, Index, DateTime
from sqlalchemy.dialects.postgresql import UUID, INET
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.models.base import BaseModel


class AuditAction(enum.Enum):
    """Audit action types"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    READ = "read"
    EXPORT = "export"
    LOGIN = "login"
    LOGOUT = "logout"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    CAMPAIGN_STARTED = "campaign_started"
    CAMPAIGN_PAUSED = "campaign_paused"
    CAMPAIGN_COMPLETED = "campaign_completed"
    LEAD_QUALIFIED = "lead_qualified"
    LEAD_CONVERTED = "lead_converted"
    EMAIL_SENT = "email_sent"
    WEBHOOK_TRIGGERED = "webhook_triggered"


class AuditLog(BaseModel):
    """Audit log model - tracks all important actions"""
    
    __tablename__ = "audit_logs"
    
    # Who performed the action
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    user_email = Column(String(255), nullable=True)
    user_role = Column(String(50), nullable=True)
    
    # What action was performed
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(50), nullable=False, index=True)  # lead, campaign, user, etc.
    resource_id = Column(String(255), nullable=True, index=True)
    
    # Details
    old_value = Column(JSON, nullable=True)  # Before state
    new_value = Column(JSON, nullable=True)  # After state
    changes = Column(JSON, nullable=True)  # Summary of changes
    
    # Request context
    request_id = Column(String(100), nullable=True, index=True)
    ip_address = Column(INET, nullable=True)
    user_agent = Column(String(500), nullable=True)
    endpoint = Column(String(500), nullable=True)
    method = Column(String(10), nullable=True)
    
    # Status
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Duration
    duration_ms = Column(Integer, nullable=True)
    
    # Indexes
    __table_args__ = (
        Index("idx_audit_user_time", "user_id", "created_at"),
        Index("idx_audit_resource", "resource_type", "resource_id"),
        Index("idx_audit_action_time", "action", "created_at"),
    )
    
    def __repr__(self):
        return f"<AuditLog {self.action} on {self.resource_type} by {self.user_email}>"


class AuditService:
    """Helper service to create audit logs"""
    
    @staticmethod
    async def log(
        db,
        action: AuditAction,
        resource_type: str,
        resource_id: str = None,
        user_id: str = None,
        user_email: str = None,
        old_value: dict = None,
        new_value: dict = None,
        request = None,
        success: bool = True,
        error_message: str = None,
        duration_ms: int = None
    ):
        """Create an audit log entry"""
        
        audit = AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action.value if isinstance(action, AuditAction) else action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id else None,
            old_value=old_value,
            new_value=new_value,
            changes=AuditService._compute_changes(old_value, new_value),
            success=success,
            error_message=error_message,
            duration_ms=duration_ms
        )
        
        if request:
            audit.request_id = getattr(request.state, 'request_id', None)
            audit.ip_address = request.client.host if request.client else None
            audit.user_agent = request.headers.get("user-agent")
            audit.endpoint = request.url.path
            audit.method = request.method
        
        db.add(audit)
        await db.commit()
        
        return audit
    
    @staticmethod
    def _compute_changes(old: dict, new: dict) -> dict:
        """Compute changes between old and new values"""
        if not old or not new:
            return None
        
        changes = {}
        for key in set(old.keys()) | set(new.keys()):
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val:
                changes[key] = {"old": old_val, "new": new_val}
        
        return changes if changes else None