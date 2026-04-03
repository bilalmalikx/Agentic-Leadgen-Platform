"""
Campaign Service
Business logic for campaign management and orchestration
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.campaign import Campaign, CampaignStatus, CampaignPriority
from app.models.lead import Lead, LeadStatus, LeadQuality
from app.models.scraping_job import ScrapingJob, JobStatus, SourceType
from app.schemas.campaign import CampaignCreate, CampaignUpdate
from app.db.repositories.campaign_repository import CampaignRepository
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class CampaignService:
    """Service for campaign business logic"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repository = CampaignRepository(db)
    
    async def get_campaigns(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[Campaign], int]:
        """Get campaigns for user"""
        return await self.repository.get_by_user(
            user_id=user_id,
            status=status,
            offset=offset,
            limit=limit
        )
    
    async def get_campaign_by_id(
        self,
        campaign_id: UUID,
        user_id: Optional[UUID] = None
    ) -> Optional[Campaign]:
        """Get campaign by ID"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if campaign and user_id and campaign.created_by != user_id:
            return None
        
        return campaign
    
    async def create_campaign(
        self,
        campaign_data: Dict[str, Any],
        user_id: UUID
    ) -> Campaign:
        """Create a new campaign"""
        campaign_data["created_by"] = user_id
        campaign_data["status"] = CampaignStatus.DRAFT
        
        campaign = await self.repository.create(campaign_data)
        logger.info(f"Campaign created: {campaign.name} by user {user_id}")
        
        return campaign
    
    async def update_campaign(
        self,
        campaign_id: UUID,
        update_data: Dict[str, Any],
        user_id: UUID
    ) -> Optional[Campaign]:
        """Update an existing campaign"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if not campaign or campaign.created_by != user_id:
            return None
        
        # Don't allow updating running campaigns
        if campaign.status == CampaignStatus.RUNNING:
            raise ValueError("Cannot update a running campaign")
        
        campaign = await self.repository.update(campaign_id, update_data)
        logger.info(f"Campaign updated: {campaign.name}")
        
        return campaign
    
    async def delete_campaign(self, campaign_id: UUID, user_id: UUID) -> bool:
        """Soft delete a campaign"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if not campaign or campaign.created_by != user_id:
            return False
        
        return await self.repository.soft_delete(campaign_id)
    
    async def start_campaign(self, campaign_id: UUID) -> bool:
        """Start a campaign"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if not campaign:
            return False
        
        if campaign.status not in [CampaignStatus.DRAFT, CampaignStatus.PAUSED, CampaignStatus.SCHEDULED]:
            raise ValueError(f"Cannot start campaign with status {campaign.status}")
        
        campaign.mark_started()
        await self.repository.update(campaign_id, {
            "status": campaign.status,
            "started_at": campaign.started_at,
            "last_run_at": campaign.last_run_at
        })
        
        logger.info(f"Campaign started: {campaign.name}")
        return True
    
    async def pause_campaign(self, campaign_id: UUID) -> bool:
        """Pause a running campaign"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if not campaign or campaign.status != CampaignStatus.RUNNING:
            return False
        
        campaign.status = CampaignStatus.PAUSED
        await self.repository.update(campaign_id, {"status": campaign.status})
        
        logger.info(f"Campaign paused: {campaign.name}")
        return True
    
    async def resume_campaign(self, campaign_id: UUID) -> bool:
        """Resume a paused campaign"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if not campaign or campaign.status != CampaignStatus.PAUSED:
            return False
        
        campaign.status = CampaignStatus.RUNNING
        campaign.last_run_at = datetime.utcnow()
        await self.repository.update(campaign_id, {
            "status": campaign.status,
            "last_run_at": campaign.last_run_at
        })
        
        logger.info(f"Campaign resumed: {campaign.name}")
        return True
    
    async def cancel_campaign(self, campaign_id: UUID) -> bool:
        """Cancel a campaign"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if not campaign:
            return False
        
        if campaign.status in [CampaignStatus.COMPLETED, CampaignStatus.CANCELLED]:
            return False
        
        campaign.status = CampaignStatus.CANCELLED
        campaign.completed_at = datetime.utcnow()
        await self.repository.update(campaign_id, {
            "status": campaign.status,
            "completed_at": campaign.completed_at
        })
        
        logger.info(f"Campaign cancelled: {campaign.name}")
        return True
    
    async def schedule_campaign(
        self,
        campaign_id: UUID,
        scheduled_at: datetime
    ) -> bool:
        """Schedule a campaign for later"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if not campaign:
            return False
        
        campaign.status = CampaignStatus.SCHEDULED
        campaign.scheduled_start_at = scheduled_at
        await self.repository.update(campaign_id, {
            "status": campaign.status,
            "scheduled_start_at": campaign.scheduled_start_at
        })
        
        logger.info(f"Campaign scheduled: {campaign.name} for {scheduled_at}")
        return True
    
    async def get_campaign_leads(
        self,
        campaign_id: UUID,
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[Lead], int]:
        """Get leads generated by a campaign"""
        # Get leads query
        query = select(Lead).where(
            Lead.campaign_id == campaign_id,
            Lead.is_deleted == False
        )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.execute(count_query)
        total = total.scalar_one()
        
        # Apply pagination
        query = query.offset(offset).limit(limit)
        
        # Execute query
        result = await self.db.execute(query)
        leads = result.scalars().all()
        
        return leads, total
    
    async def get_campaign_stats(self, campaign_id: UUID) -> Optional[Dict[str, Any]]:
        """Get detailed campaign statistics"""
        campaign = await self.repository.get_by_id(campaign_id)
        
        if not campaign:
            return None
        
        # Lead statistics
        lead_stats_query = select(
            func.count(Lead.id).label("total"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.QUALIFIED).label("qualified"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.CONTACTED).label("contacted"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.CONVERTED).label("converted"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.REJECTED).label("rejected"),
            func.avg(Lead.score).label("avg_score")
        ).where(Lead.campaign_id == campaign_id)
        
        result = await self.db.execute(lead_stats_query)
        stats = result.one()
        
        # Leads by source
        source_query = select(
            Lead.source,
            func.count(Lead.id).label("count")
        ).where(Lead.campaign_id == campaign_id).group_by(Lead.source)
        
        source_result = await self.db.execute(source_query)
        leads_by_source = {row.source.value: row.count for row in source_result}
        
        # Leads by quality
        quality_query = select(
            Lead.quality,
            func.count(Lead.id).label("count")
        ).where(Lead.campaign_id == campaign_id).group_by(Lead.quality)
        
        quality_result = await self.db.execute(quality_query)
        leads_by_quality = {row.quality.value: row.count for row in quality_result}
        
        # Top companies
        company_query = select(
            Lead.company_name,
            func.count(Lead.id).label("count")
        ).where(
            Lead.campaign_id == campaign_id,
            Lead.company_name.isnot(None)
        ).group_by(Lead.company_name).order_by(func.count(Lead.id).desc()).limit(10)
        
        company_result = await self.db.execute(company_query)
        top_companies = [{"company": row.company_name, "count": row.count} for row in company_result]
        
        # Scraping jobs summary
        jobs_query = select(
            ScrapingJob.source,
            ScrapingJob.status,
            func.sum(ScrapingJob.items_scraped).label("total_scraped")
        ).where(ScrapingJob.campaign_id == campaign_id).group_by(ScrapingJob.source, ScrapingJob.status)
        
        jobs_result = await self.db.execute(jobs_query)
        scraping_summary = [
            {
                "source": row.source.value,
                "status": row.status.value,
                "items_scraped": row.total_scraped or 0
            }
            for row in jobs_result
        ]
        
        return {
            "campaign_id": str(campaign_id),
            "campaign_name": campaign.name,
            "status": campaign.status.value,
            "progress": campaign.get_progress(),
            "leads": {
                "total": stats.total or 0,
                "qualified": stats.qualified or 0,
                "contacted": stats.contacted or 0,
                "converted": stats.converted or 0,
                "rejected": stats.rejected or 0,
                "average_score": round(stats.avg_score or 0, 2)
            },
            "leads_by_source": leads_by_source,
            "leads_by_quality": leads_by_quality,
            "top_companies": top_companies,
            "scraping_jobs": scraping_summary,
            "timeline": {
                "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
                "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
                "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None
            }
        }
    
    async def get_overall_stats(self, user_id: UUID) -> Dict[str, Any]:
        """Get overall statistics across all campaigns for a user"""
        # Total campaigns
        campaigns_query = select(func.count(Campaign.id)).where(
            Campaign.created_by == user_id,
            Campaign.is_deleted == False
        )
        total_campaigns = await self.db.execute(campaigns_query)
        total_campaigns = total_campaigns.scalar_one() or 0
        
        # Running campaigns
        running_query = select(func.count(Campaign.id)).where(
            Campaign.created_by == user_id,
            Campaign.status == CampaignStatus.RUNNING
        )
        running_campaigns = await self.db.execute(running_query)
        running_campaigns = running_campaigns.scalar_one() or 0
        
        # Total leads
        leads_query = select(func.count(Lead.id)).where(
            Lead.campaign.has(created_by=user_id),
            Lead.is_deleted == False
        )
        total_leads = await self.db.execute(leads_query)
        total_leads = total_leads.scalar_one() or 0
        
        # Qualified leads
        qualified_query = select(func.count(Lead.id)).where(
            Lead.campaign.has(created_by=user_id),
            Lead.status == LeadStatus.QUALIFIED
        )
        qualified_leads = await self.db.execute(qualified_query)
        qualified_leads = qualified_leads.scalar_one() or 0
        
        return {
            "total_campaigns": total_campaigns,
            "running_campaigns": running_campaigns,
            "total_leads": total_leads,
            "qualified_leads": qualified_leads,
            "conversion_rate": round((qualified_leads / total_leads * 100) if total_leads > 0 else 0, 2)
        }
    
    async def duplicate_campaign(
        self,
        campaign_id: UUID,
        new_name: str,
        copy_leads: bool,
        user_id: UUID
    ) -> Campaign:
        """Duplicate an existing campaign"""
        original = await self.repository.get_by_id(campaign_id)
        
        if not original:
            raise ValueError(f"Campaign {campaign_id} not found")
        
        # Create new campaign from original
        new_data = {
            "name": new_name,
            "description": original.description,
            "query": original.query,
            "keywords": original.keywords,
            "locations": original.locations,
            "industries": original.industries,
            "job_titles": original.job_titles,
            "sources": original.sources,
            "source_config": original.source_config,
            "target_leads_count": original.target_leads_count,
            "max_leads_per_source": original.max_leads_per_source,
            "min_score_threshold": original.min_score_threshold,
            "enable_deduplication": original.enable_deduplication,
            "enable_enrichment": original.enable_enrichment,
            "enable_scoring": original.enable_scoring,
            "priority": original.priority,
            "webhook_url": original.webhook_url,
            "webhook_events": original.webhook_events,
            "auto_export": original.auto_export,
            "export_format": original.export_format,
            "export_destination": original.export_destination,
            "created_by": user_id,
            "status": CampaignStatus.DRAFT
        }
        
        new_campaign = await self.repository.create(new_data)
        logger.info(f"Campaign duplicated: {original.name} -> {new_campaign.name}")
        
        # Optionally copy leads (would need to deep copy lead data)
        if copy_leads:
            logger.warning("Copying leads not implemented yet")
        
        return new_campaign