"""
Base SQLAlchemy Model with Common Fields
All database models inherit from this
"""

from datetime import datetime
from sqlalchemy import Column, DateTime, String, Integer, Boolean, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.sql import func
import uuid

from app.core.database import Base


class BaseModel(Base):
    """Abstract base model with common fields"""
    
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
    
    @declared_attr
    def __tablename__(cls):
        """Generate table name from class name"""
        import re
        name = re.sub(r'(?<!^)(?=[A-Z])', '_', cls.__name__).lower()
        return f"{name}s"  # Plural form
    
    def dict(self):
        """Convert model to dictionary"""
        return {
            column.name: getattr(self, column.name)
            for column in self.__table__.columns
        }
    
    def update(self, **kwargs):
        """Update model attributes"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.utcnow()
    
    class Config:
        """Pydantic config for ORM mode"""
        from_attributes = True


class TimestampMixin:
    """Mixin for timestamp fields"""
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)


class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    def soft_delete(self):
        """Soft delete this record"""
        self.is_deleted = True
        self.deleted_at = datetime.utcnow()
    
    def restore(self):
        """Restore soft deleted record"""
        self.is_deleted = False
        self.deleted_at = None


class AuditMixin:
    """Mixin for audit fields"""
    created_by = Column(UUID(as_uuid=True), nullable=True)
    updated_by = Column(UUID(as_uuid=True), nullable=True)
    created_by_ip = Column(String(45), nullable=True)  # IPv6 support
    updated_by_ip = Column(String(45), nullable=True)


class MetadataMixin:
    """Mixin for JSON metadata field"""
    metadata = Column(JSON, default=dict, nullable=False)
    
    def get_metadata(self, key: str, default=None):
        """Get metadata value by key"""
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value):
        """Set metadata value"""
        self.metadata[key] = value