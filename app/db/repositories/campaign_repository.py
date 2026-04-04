"""
Campaign Repository
Database operations for Campaign model
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy import select, func, and_, or_

from app.db.repositories.base_repository import BaseRepository
from app.models.campaign import Campaign, CampaignStatus
from app.core.logging import get_logger

logger = get_logger(__name__)


class CampaignRepository(BaseRepository[Campaign]):
    """Repository for Campaign model operations"""
    
    def __init__(self, db):
        super().__init__(db, Campaign)
    
    async def get_by_user(
        self,
        user_id: UUID,
        status: Optional[str] = None,
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[Campaign], int]:
        """
        Get campaigns by user ID
        """
        # Build query
        query = select(self.model).where(
            self.model.created_by == user_id,
            self.model.is_deleted == False
        )
        
        # Apply status filter
        if status:
            query = query.where(self.model.status == status)
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await self.db.execute(count_query)
        total = total.scalar_one()
        
        # Apply pagination
        query = query.order_by(self.model.created_at.desc()).offset(offset).limit(limit)
        
        # Execute query
        result = await self.db.execute(query)
        campaigns = result.scalars().all()
        
        return campaigns, total
    
    async def get_running_campaigns(self) -> List[Campaign]:
        """
        Get all running campaigns
        """
        query = select(self.model).where(
            self.model.status == CampaignStatus.RUNNING,
            self.model.is_deleted == False
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_scheduled_campaigns(self) -> List[Campaign]:
        """
        Get all scheduled campaigns ready to start
        """
        query = select(self.model).where(
            self.model.status == CampaignStatus.SCHEDULED,
            self.model.scheduled_start_at <= datetime.utcnow(),
            self.model.is_deleted == False
        )
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def update_status(
        self,
        campaign_id: UUID,
        status: CampaignStatus,
        error_message: Optional[str] = None
    ) -> Optional[Campaign]:
        """
        Update campaign status
        """
        data = {"status": status}
        
        if status == CampaignStatus.RUNNING:
            data["started_at"] = datetime.utcnow()
            data["last_run_at"] = datetime.utcnow()
        elif status == CampaignStatus.COMPLETED:
            data["completed_at"] = datetime.utcnow()
            data["progress_percentage"] = 100
        elif status == CampaignStatus.FAILED:
            data["completed_at"] = datetime.utcnow()
            if error_message:
                data["error_message"] = error_message
        
        return await self.update(campaign_id, data)
    
    async def update_progress(
        self,
        campaign_id: UUID,
        leads_found: int,
        leads_added: int,
        duplicates: int,
        failed: int
    ) -> Optional[Campaign]:
        """
        Update campaign progress
        """
        campaign = await self.get_by_id(campaign_id)
        
        if not campaign:
            return None
        
        data = {
            "total_leads_found": campaign.total_leads_found + leads_found,
            "unique_leads_added": campaign.unique_leads_added + leads_added,
            "duplicate_leads_skipped": campaign.duplicate_leads_skipped + duplicates,
            "failed_scrapes": campaign.failed_scrapes + failed
        }
        
        # Update progress percentage
        if campaign.target_leads_count > 0:
            data["progress_percentage"] = min(100, int(
                (data["unique_leads_added"] / campaign.target_leads_count) * 100
            ))
        
        return await self.update(campaign_id, data)
    
    async def get_campaign_stats(self, user_id: UUID) -> Dict[str, Any]:
        """
        Get campaign statistics for a user
        """
        query = select(
            func.count(self.model.id).label("total"),
            func.count(self.model.id).filter(self.model.status == CampaignStatus.RUNNING).label("running"),
            func.count(self.model.id).filter(self.model.status == CampaignStatus.COMPLETED).label("completed"),
            func.count(self.model.id).filter(self.model.status == CampaignStatus.FAILED).label("failed"),
            func.sum(self.model.total_leads_found).label("total_leads_found"),
            func.sum(self.model.unique_leads_added).label("total_leads_added")
        ).where(
            self.model.created_by == user_id,
            self.model.is_deleted == False
        )
        
        result = await self.db.execute(query)
        stats = result.one()
        
        return {
            "total_campaigns": stats.total or 0,
            "running_campaigns": stats.running or 0,
            "completed_campaigns": stats.completed or 0,
            "failed_campaigns": stats.failed or 0,
            "total_leads_found": stats.total_leads_found or 0,
            "total_leads_added": stats.total_leads_added or 0
        }
    
    async def search_campaigns(
        self,
        user_id: UUID,
        search_term: str,
        limit: int = 20
    ) -> List[Campaign]:
        """
        Search campaigns by name or description
        """
        search_pattern = f"%{search_term}%"
        
        query = select(self.model).where(
            self.model.created_by == user_id,
            self.model.is_deleted == False,
            or_(
                self.model.name.ilike(search_pattern),
                self.model.description.ilike(search_pattern)
            )
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()