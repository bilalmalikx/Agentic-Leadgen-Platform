#!/usr/bin/env python3
"""
Cleanup Old Leads Script
Soft delete leads older than specified days
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_sync_session
from app.core.logging import get_logger
from app.models.lead import Lead

logger = get_logger(__name__)


def cleanup_old_leads(days: int = 90, dry_run: bool = True):
    """
    Delete leads older than specified days
    
    Args:
        days: Age in days
        dry_run: If True, only show what would be deleted
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    with get_sync_session() as db:
        # Find old leads
        old_leads = db.query(Lead).filter(
            Lead.created_at < cutoff_date,
            Lead.is_deleted == False
        ).all()
        
        print(f"\n📊 Found {len(old_leads)} leads older than {days} days")
        
        if dry_run:
            print("\n🔍 DRY RUN - No changes will be made")
            for lead in old_leads[:10]:
                print(f"   - {lead.email} (created: {lead.created_at})")
            
            if len(old_leads) > 10:
                print(f"   ... and {len(old_leads) - 10} more")
            
            print(f"\n💡 To actually delete, run: python scripts/cleanup_old_leads.py --days {days} --execute")
        else:
            # Soft delete
            for lead in old_leads:
                lead.is_deleted = True
                lead.deleted_at = datetime.utcnow()
            
            db.commit()
            print(f"\n✅ Soft deleted {len(old_leads)} leads")
    
    return len(old_leads)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean up old leads")
    parser.add_argument("--days", type=int, default=90, help="Days to keep (default: 90)")
    parser.add_argument("--execute", action="store_true", help="Actually delete (dry run by default)")
    
    args = parser.parse_args()
    
    cleanup_old_leads(days=args.days, dry_run=not args.execute)