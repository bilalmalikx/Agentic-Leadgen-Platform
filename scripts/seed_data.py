#!/usr/bin/env python3
"""
Seed Database Script
Populates database with demo data for testing
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta
import random

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import get_sync_session
from app.core.security import get_password_hash
from app.models.user import User, UserRole, UserStatus
from app.models.campaign import Campaign, CampaignStatus, CampaignPriority
from app.models.lead import Lead, LeadStatus, LeadSource, LeadQuality

logger = get_logger(__name__)


def seed_users():
    """Create demo users"""
    print("📊 Seeding users...")
    
    with get_sync_session() as db:
        users = [
            User(
                email="admin@leadgen.com",
                password_hash=get_password_hash("Admin@123"),
                full_name="Admin User",
                role=UserRole.ADMIN,
                status=UserStatus.ACTIVE,
                monthly_lead_quota=10000
            ),
            User(
                email="user@leadgen.com",
                password_hash=get_password_hash("User@123"),
                full_name="Demo User",
                role=UserRole.USER,
                status=UserStatus.ACTIVE,
                monthly_lead_quota=1000
            )
        ]
        
        for user in users:
            existing = db.query(User).filter(User.email == user.email).first()
            if not existing:
                db.add(user)
        
        db.commit()
        print("✅ Users seeded")


def seed_campaigns():
    """Create demo campaigns"""
    print("📊 Seeding campaigns...")
    
    with get_sync_session() as db:
        user = db.query(User).filter(User.email == "admin@leadgen.com").first()
        
        if not user:
            print("⚠️  No user found, skipping campaigns")
            return
        
        campaigns = [
            Campaign(
                name="AI SaaS Founders",
                description="Find founders of AI SaaS companies",
                query="founder of AI startup CTO of AI company",
                sources=["linkedin", "twitter"],
                target_leads_count=500,
                status=CampaignStatus.COMPLETED,
                priority=CampaignPriority.HIGH,
                created_by=user.id,
                total_leads_found=500,
                unique_leads_added=450,
                completed_at=datetime.utcnow() - timedelta(days=5)
            ),
            Campaign(
                name="Tech CTOs Europe",
                description="CTOs at tech companies in Europe",
                query="CTO technology company Europe",
                sources=["linkedin", "crunchbase"],
                target_leads_count=300,
                status=CampaignStatus.RUNNING,
                priority=CampaignPriority.MEDIUM,
                created_by=user.id,
                started_at=datetime.utcnow() - timedelta(days=2)
            ),
            Campaign(
                name="HealthTech Leaders",
                description="Leaders in HealthTech industry",
                query="CEO founder HealthTech",
                sources=["linkedin", "twitter", "crunchbase"],
                target_leads_count=200,
                status=CampaignStatus.DRAFT,
                priority=CampaignPriority.LOW,
                created_by=user.id
            )
        ]
        
        for campaign in campaigns:
            db.add(campaign)
        
        db.commit()
        print("✅ Campaigns seeded")


def seed_leads():
    """Create demo leads"""
    print("📊 Seeding leads...")
    
    with get_sync_session() as db:
        campaign = db.query(Campaign).first()
        
        if not campaign:
            print("⚠️  No campaign found, skipping leads")
            return
        
        companies = ["Tech Corp", "AI Solutions", "DataFlow", "CloudNine", "SmartSoft"]
        titles = ["CEO", "CTO", "Founder", "VP Engineering", "Director"]
        qualities = ["hot", "warm", "cold", "unqualified"]
        
        for i in range(50):
            lead = Lead(
                email=f"lead{i}@example.com",
                first_name=f"First{i}",
                last_name=f"Last{i}",
                full_name=f"First{i} Last{i}",
                company_name=random.choice(companies),
                job_title=random.choice(titles),
                score=random.randint(20, 95),
                quality=random.choice(qualities),
                status=random.choice([LeadStatus.NEW, LeadStatus.QUALIFIED, LeadStatus.CONTACTED]),
                source=random.choice([LeadSource.LINKEDIN, LeadSource.TWITTER, LeadSource.CRUNCHBASE]),
                campaign_id=campaign.id,
                created_at=datetime.utcnow() - timedelta(days=random.randint(1, 30))
            )
            db.add(lead)
        
        db.commit()
        print("✅ Leads seeded")


if __name__ == "__main__":
    print("=" * 50)
    print("LeadGen Database Seeding")
    print("=" * 50)
    
    seed_users()
    seed_campaigns()
    seed_leads()
    
    print("\n✅ Seeding completed!")