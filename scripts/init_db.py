#!/usr/bin/env python3
"""
Database Initialization Script
Creates tables and initial data
"""

import sys
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import engine, Base
from app.core.logging import get_logger
from app.models import (
    Lead, Campaign, User, ScrapingJob, 
    EmailLog, AuditLog, WebhookDelivery
)

logger = get_logger(__name__)


def init_database():
    """Create all database tables"""
    print("\n📊 Initializing database...")
    
    try:
        # Create all tables
        Base.metadata.create_all(bind=engine)
        print("✅ Database tables created successfully")
        
        # Verify tables
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"\n📋 Created tables: {', '.join(tables)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database initialization failed: {e}")
        return False


def create_default_user():
    """Create default admin user"""
    from app.core.security import get_password_hash
    from app.db.session import get_sync_session
    from app.models.user import User, UserRole, UserStatus
    
    with get_sync_session() as db:
        # Check if user exists
        existing = db.query(User).filter(User.email == "admin@leadgen.com").first()
        
        if existing:
            print("⚠️  Default user already exists")
            return
        
        # Create admin user
        admin = User(
            email="admin@leadgen.com",
            password_hash=get_password_hash(os.getenv("ADMIN_PASSWORD", "CHANGE_ME_NOW")),
            full_name="System Administrator",
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE,
            monthly_lead_quota=10000
        )
        
        db.add(admin)
        db.commit()
        
        print("✅ Default admin user created:")
        print("   Email: admin@leadgen.com")
        print("   Password: Admin@123")


if __name__ == "__main__":
    print("=" * 50)
    print("LeadGen Database Initialization")
    print("=" * 50)
    
    if init_database():
        create_default_user()
        print("\n✅ Database initialization completed!")
    else:
        print("\n❌ Database initialization failed!")
        sys.exit(1)