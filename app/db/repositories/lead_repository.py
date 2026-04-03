"""
Lead Repository
Database operations for Lead model using repository pattern
"""

from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_

from app.models.lead import Lead, LeadStatus, LeadSource, LeadQuality
from app.db.repositories.base_repository import BaseRepository
from app.core.logging import get_logger

logger = get_logger(__name__)


class LeadRepository(BaseRepository[Lead]):
    """Repository for Lead model operations"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(db, Lead)
    
    async def get_by_email(self, email: str) -> Optional[Lead]:
        """Get lead by email address"""
        query = select(Lead).where(
            Lead.email.ilike(email),
            Lead.is_deleted == False
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_campaign(
        self,
        campaign_id: UUID,
        offset: int = 0,
        limit: int = 100
    ) -> Tuple[List[Lead], int]:
        """Get all leads for a campaign"""
        # Get total count
        count_query = select(func.count()).select_from(Lead).where(
            Lead.campaign_id == campaign_id,
            Lead.is_deleted == False
        )
        total = await self.db.execute(count_query)
        total = total.scalar_one()
        
        # Get leads
        query = select(Lead).where(
            Lead.campaign_id == campaign_id,
            Lead.is_deleted == False
        ).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        leads = result.scalars().all()
        
        return leads, total
    
    async def get_by_status(
        self,
        status: LeadStatus,
        limit: int = 100
    ) -> List[Lead]:
        """Get leads by status"""
        query = select(Lead).where(
            Lead.status == status,
            Lead.is_deleted == False
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_by_quality(
        self,
        quality: LeadQuality,
        limit: int = 100
    ) -> List[Lead]:
        """Get leads by quality"""
        query = select(Lead).where(
            Lead.quality == quality,
            Lead.is_deleted == False
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_high_value_leads(self, min_score: int = 80, limit: int = 50) -> List[Lead]:
        """Get high-value leads (hot leads)"""
        query = select(Lead).where(
            Lead.score >= min_score,
            Lead.is_deleted == False,
            Lead.status != LeadStatus.CONVERTED
        ).order_by(Lead.score.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def search_by_keyword(
        self,
        keyword: str,
        offset: int = 0,
        limit: int = 20
    ) -> Tuple[List[Lead], int]:
        """Search leads by keyword in multiple fields"""
        search_pattern = f"%{keyword}%"
        
        # Count query
        count_query = select(func.count()).select_from(Lead).where(
            or_(
                Lead.full_name.ilike(search_pattern),
                Lead.email.ilike(search_pattern),
                Lead.company_name.ilike(search_pattern),
                Lead.job_title.ilike(search_pattern),
                Lead.industry.ilike(search_pattern)
            ),
            Lead.is_deleted == False
        )
        total = await self.db.execute(count_query)
        total = total.scalar_one()
        
        # Data query
        query = select(Lead).where(
            or_(
                Lead.full_name.ilike(search_pattern),
                Lead.email.ilike(search_pattern),
                Lead.company_name.ilike(search_pattern),
                Lead.job_title.ilike(search_pattern),
                Lead.industry.ilike(search_pattern)
            ),
            Lead.is_deleted == False
        ).offset(offset).limit(limit)
        
        result = await self.db.execute(query)
        leads = result.scalars().all()
        
        return leads, total
    
    async def update_score(self, lead_id: UUID, score: int) -> Optional[Lead]:
        """Update lead score and recalculate quality"""
        # Determine quality based on score
        if score >= 80:
            quality = LeadQuality.HOT
        elif score >= 60:
            quality = LeadQuality.WARM
        elif score >= 40:
            quality = LeadQuality.COLD
        else:
            quality = LeadQuality.UNQUALIFIED
        
        return await self.update(
            lead_id,
            {"score": score, "quality": quality}
        )
    
    async def bulk_update_status(
        self,
        lead_ids: List[UUID],
        status: LeadStatus
    ) -> int:
        """Bulk update lead status"""
        query = update(Lead).where(
            Lead.id.in_(lead_ids),
            Lead.is_deleted == False
        ).values(status=status, updated_at=datetime.utcnow())
        
        result = await self.db.execute(query)
        await self.db.commit()
        
        return result.rowcount
    
    async def get_stats_by_campaign(self, campaign_id: UUID) -> Dict[str, Any]:
        """Get lead statistics for a campaign"""
        query = select(
            func.count(Lead.id).label("total"),
            func.avg(Lead.score).label("avg_score"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.QUALIFIED).label("qualified"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.CONTACTED).label("contacted"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.CONVERTED).label("converted"),
            func.count(Lead.id).filter(Lead.status == LeadStatus.REJECTED).label("rejected"),
            func.count(Lead.id).filter(Lead.quality == LeadQuality.HOT).label("hot"),
            func.count(Lead.id).filter(Lead.quality == LeadQuality.WARM).label("warm"),
            func.count(Lead.id).filter(Lead.quality == LeadQuality.COLD).label("cold")
        ).where(
            Lead.campaign_id == campaign_id,
            Lead.is_deleted == False
        )
        
        result = await self.db.execute(query)
        stats = result.one()
        
        return {
            "total": stats.total or 0,
            "average_score": round(stats.avg_score or 0, 2),
            "qualified": stats.qualified or 0,
            "contacted": stats.contacted or 0,
            "converted": stats.converted or 0,
            "rejected": stats.rejected or 0,
            "hot": stats.hot or 0,
            "warm": stats.warm or 0,
            "cold": stats.cold or 0
        }
    
    async def find_duplicates(
        self,
        email: str,
        similarity_threshold: float = 0.8
    ) -> List[Lead]:
        """Find potential duplicate leads by email similarity"""
        # Exact email match
        exact_matches = await self.get_by_email(email)
        
        # Fuzzy email match (using ILIKE)
        email_parts = email.split('@')[0]
        fuzzy_query = select(Lead).where(
            Lead.email.ilike(f"%{email_parts}%@%"),
            Lead.is_deleted == False
        ).limit(10)
        
        result = await self.db.execute(fuzzy_query)
        fuzzy_matches = result.scalars().all()
        
        # Combine and deduplicate
        all_matches = []
        seen_ids = set()
        
        if exact_matches and exact_matches.id not in seen_ids:
            seen_ids.add(exact_matches.id)
            all_matches.append(exact_matches)
        
        for lead in fuzzy_matches:
            if lead.id not in seen_ids:
                seen_ids.add(lead.id)
                all_matches.append(lead)
        
        return all_matches
    
    async def get_pending_enrichment(self, limit: int = 100) -> List[Lead]:
        """Get leads that need enrichment"""
        query = select(Lead).where(
            Lead.enriched_data == {},
            Lead.is_deleted == False
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_untouched_leads(self, days: int = 7, limit: int = 100) -> List[Lead]:
        """Get leads not updated in X days"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = select(Lead).where(
            Lead.updated_at <= cutoff,
            Lead.is_deleted == False,
            Lead.status == LeadStatus.NEW
        ).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()