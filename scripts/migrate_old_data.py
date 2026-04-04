#!/usr/bin/env python3
"""
Data Migration Script
Migrate data from old schema to new schema
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_sync_session
from app.core.logging import get_logger

logger = get_logger(__name__)


def migrate_leads():
    """Migrate leads data"""
    print("\n📊 Migrating leads...")
    
    with get_sync_session() as db:
        # Add migration logic here
        # Example: update status values, add new fields, etc.
        
        from app.models.lead import Lead
        
        # Update leads without quality
        leads = db.query(Lead).filter(Lead.quality.is_(None)).all()
        
        for lead in leads:
            if lead.score >= 80:
                lead.quality = "hot"
            elif lead.score >= 60:
                lead.quality = "warm"
            elif lead.score >= 40:
                lead.quality = "cold"
            else:
                lead.quality = "unqualified"
        
        db.commit()
        print(f"✅ Updated quality for {len(leads)} leads")


def migrate_campaigns():
    """Migrate campaigns data"""
    print("\n📊 Migrating campaigns...")
    
    with get_sync_session() as db:
        from app.models.campaign import Campaign
        
        # Add migration logic here
        campaigns = db.query(Campaign).all()
        
        for campaign in campaigns:
            if campaign.progress_percentage is None:
                campaign.progress_percentage = 0
        
        db.commit()
        print(f"✅ Updated {len(campaigns)} campaigns")


if __name__ == "__main__":
    print("=" * 50)
    print("LeadGen Data Migration")
    print("=" * 50)
    
    migrate_leads()
    migrate_campaigns()
    
    print("\n✅ Migration completed!")