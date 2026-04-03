"""
Analytics Service
Aggregates statistics and generates reports for dashboards
"""

from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, between, case

from app.core.logging import get_logger
from app.models.lead import Lead, LeadStatus, LeadQuality, LeadSource
from app.models.campaign import Campaign, CampaignStatus
from app.db.repositories.lead_repository import LeadRepository
from app.db.repositories.campaign_repository import CampaignRepository

logger = get_logger(__name__)


class AnalyticsService:
    """Service for analytics and reporting"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.campaign_repo = CampaignRepository(db)
    
    async def get_dashboard_summary(self, user_id: UUID) -> Dict[str, Any]:
        """Get dashboard summary statistics for a user"""
        
        # Get campaigns
        campaigns, _ = await self.campaign_repo.get_by_user(user_id=user_id)
        total_campaigns = len(campaigns)
        active_campaigns = len([c for c in campaigns if c.status == CampaignStatus.RUNNING])
        
        # Get leads stats
        lead_stats = await self.lead_repo.get_stats_by_user(user_id)
        
        # Get leads today
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        leads_today_query = select(func.count(Lead.id)).where(
            Lead.created_by == user_id,
            Lead.created_at >= today_start,
            Lead.is_deleted == False
        )
        leads_today = await self.db.execute(leads_today_query)
        leads_today = leads_today.scalar_one() or 0
        
        # Get leads this week
        week_start = datetime.utcnow() - timedelta(days=7)
        leads_week_query = select(func.count(Lead.id)).where(
            Lead.created_by == user_id,
            Lead.created_at >= week_start,
            Lead.is_deleted == False
        )
        leads_this_week = await self.db.execute(leads_week_query)
        leads_this_week = leads_this_week.scalar_one() or 0
        
        # Get leads this month
        month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        leads_month_query = select(func.count(Lead.id)).where(
            Lead.created_by == user_id,
            Lead.created_at >= month_start,
            Lead.is_deleted == False
        )
        leads_this_month = await self.db.execute(leads_month_query)
        leads_this_month = leads_this_month.scalar_one() or 0
        
        # Get top performing campaign
        top_campaign = await self._get_top_campaign(user_id)
        
        return {
            "total_campaigns": total_campaigns,
            "active_campaigns": active_campaigns,
            "total_leads": lead_stats.get("total", 0),
            "qualified_leads": lead_stats.get("qualified", 0),
            "converted_leads": lead_stats.get("converted", 0),
            "average_lead_score": lead_stats.get("average_score", 0),
            "leads_today": leads_today,
            "leads_this_week": leads_this_week,
            "leads_this_month": leads_this_month,
            "top_performing_campaign": top_campaign
        }
    
    async def get_lead_generation_trend(
        self,
        user_id: UUID,
        days: int = 30,
        granularity: str = "day"
    ) -> List[Dict[str, Any]]:
        """Get lead generation trend over time"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Build query based on granularity
        if granularity == "hour":
            date_trunc = func.date_trunc('hour', Lead.created_at)
        elif granularity == "day":
            date_trunc = func.date_trunc('day', Lead.created_at)
        elif granularity == "week":
            date_trunc = func.date_trunc('week', Lead.created_at)
        else:
            date_trunc = func.date_trunc('day', Lead.created_at)
        
        query = select(
            date_trunc.label("period"),
            func.count(Lead.id).label("count")
        ).where(
            Lead.created_by == user_id,
            Lead.created_at >= start_date,
            Lead.is_deleted == False
        ).group_by("period").order_by("period")
        
        result = await self.db.execute(query)
        rows = result.all()
        
        return [
            {
                "period": row.period.isoformat() if row.period else None,
                "count": row.count
            }
            for row in rows
        ]
    
    async def get_score_distribution(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get distribution of lead scores"""
        
        ranges = [
            (0, 20), (21, 40), (41, 60), (61, 80), (81, 100)
        ]
        
        distribution = []
        
        for low, high in ranges:
            query = select(func.count(Lead.id)).where(
                Lead.created_by == user_id,
                Lead.score.between(low, high),
                Lead.is_deleted == False
            )
            count = await self.db.execute(query)
            count = count.scalar_one() or 0
            
            distribution.append({
                "range": f"{low}-{high}",
                "count": count,
                "percentage": 0  # Will calculate after total
            })
        
        total = sum(d["count"] for d in distribution)
        for d in distribution:
            d["percentage"] = round((d["count"] / total * 100), 2) if total > 0 else 0
        
        return distribution
    
    async def get_conversion_funnel(self, user_id: UUID) -> List[Dict[str, Any]]:
        """Get conversion funnel from lead creation to conversion"""
        
        stages = [
            {"name": "lead_created", "filter": LeadStatus.NEW},
            {"name": "contacted", "filter": LeadStatus.CONTACTED},
            {"name": "qualified", "filter": LeadStatus.QUALIFIED},
            {"name": "converted", "filter": LeadStatus.CONVERTED}
        ]
        
        funnel = []
        previous_count = None
        
        for stage in stages:
            query = select(func.count(Lead.id)).where(
                Lead.created_by == user_id,
                Lead.status == stage["filter"],
                Lead.is_deleted == False
            )
            count = await self.db.execute(query)
            count = count.scalar_one() or 0
            
            conversion_from_previous = 100.0
            if previous_count and previous_count > 0:
                conversion_from_previous = round((count / previous_count) * 100, 2)
            
            funnel.append({
                "stage": stage["name"],
                "count": count,
                "conversion_rate_from_previous": conversion_from_previous,
                "conversion_rate_from_start": round((count / funnel[0]["count"] * 100), 2) if funnel and funnel[0]["count"] > 0 else 100.0
            })
            
            previous_count = count
        
        return funnel
    
    async def get_leads_by_source(self, user_id: UUID) -> Dict[str, int]:
        """Get lead count grouped by source"""
        
        query = select(
            Lead.source,
            func.count(Lead.id).label("count")
        ).where(
            Lead.created_by == user_id,
            Lead.is_deleted == False
        ).group_by(Lead.source)
        
        result = await self.db.execute(query)
        
        return {row.source.value: row.count for row in result}
    
    async def get_leads_by_quality(self, user_id: UUID) -> Dict[str, int]:
        """Get lead count grouped by quality"""
        
        query = select(
            Lead.quality,
            func.count(Lead.id).label("count")
        ).where(
            Lead.created_by == user_id,
            Lead.is_deleted == False
        ).group_by(Lead.quality)
        
        result = await self.db.execute(query)
        
        return {row.quality.value: row.count for row in result}
    
    async def get_top_companies(
        self,
        user_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get top companies by lead count"""
        
        query = select(
            Lead.company_name,
            func.count(Lead.id).label("count"),
            func.avg(Lead.score).label("avg_score")
        ).where(
            Lead.created_by == user_id,
            Lead.company_name.isnot(None),
            Lead.is_deleted == False
        ).group_by(Lead.company_name).order_by(
            func.count(Lead.id).desc()
        ).limit(limit)
        
        result = await self.db.execute(query)
        
        return [
            {
                "company_name": row.company_name,
                "lead_count": row.count,
                "average_score": round(row.avg_score or 0, 2)
            }
            for row in result
        ]
    
    async def get_campaign_performance(
        self,
        user_id: UUID,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get campaign performance metrics"""
        
        campaigns, _ = await self.campaign_repo.get_by_user(user_id=user_id, limit=limit)
        
        performance = []
        for campaign in campaigns:
            stats = await self.lead_repo.get_stats_by_campaign(campaign.id)
            
            performance.append({
                "campaign_id": str(campaign.id),
                "campaign_name": campaign.name,
                "status": campaign.status.value,
                "total_leads": stats.get("total", 0),
                "qualified_leads": stats.get("qualified", 0),
                "converted_leads": stats.get("converted", 0),
                "conversion_rate": round((stats.get("converted", 0) / stats.get("total", 1)) * 100, 2),
                "average_score": stats.get("average_score", 0),
                "duration_hours": self._calculate_duration_hours(campaign),
                "leads_per_hour": self._calculate_leads_per_hour(campaign, stats.get("total", 0))
            })
        
        return performance
    
    async def get_realtime_metrics(self) -> Dict[str, Any]:
        """Get real-time system metrics"""
        
        from app.core.redis_client import cache_get
        from app.core.celery_app import celery_app
        
        # Get queue size
        inspection = celery_app.control.inspect()
        active_queues = inspection.active_queues()
        queue_size = len(active_queues) if active_queues else 0
        
        # Get active workers
        active_workers = inspection.active()
        worker_count = len(active_workers) if active_workers else 0
        
        # Get leads per minute (last 5 minutes)
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
        leads_query = select(func.count(Lead.id)).where(Lead.created_at >= five_min_ago)
        leads_last_5min = await self.db.execute(leads_query)
        leads_last_5min = leads_last_5min.scalar_one() or 0
        leads_per_minute = round(leads_last_5min / 5, 2)
        
        return {
            "leads_per_minute": leads_per_minute,
            "active_campaigns": await self._get_active_campaigns_count(),
            "queue_size": queue_size,
            "active_workers": worker_count,
            "api_requests_per_minute": await self._get_api_requests_per_minute(),
            "average_response_time_ms": await self._get_average_response_time(),
            "error_rate_percentage": await self._get_error_rate(),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _calculate_duration_hours(self, campaign: Campaign) -> float:
        """Calculate campaign duration in hours"""
        if campaign.started_at and campaign.completed_at:
            duration = campaign.completed_at - campaign.started_at
            return round(duration.total_seconds() / 3600, 2)
        return 0.0
    
    def _calculate_leads_per_hour(self, campaign: Campaign, total_leads: int) -> float:
        """Calculate leads generated per hour"""
        duration_hours = self._calculate_duration_hours(campaign)
        if duration_hours > 0:
            return round(total_leads / duration_hours, 2)
        return 0.0
    
    async def _get_top_campaign(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get top performing campaign for user"""
        campaigns = await self.get_campaign_performance(user_id, limit=1)
        return campaigns[0] if campaigns else None
    
    async def _get_active_campaigns_count(self) -> int:
        """Get count of active campaigns"""
        query = select(func.count(Campaign.id)).where(
            Campaign.status == CampaignStatus.RUNNING
        )
        result = await self.db.execute(query)
        return result.scalar_one() or 0
    
    async def _get_api_requests_per_minute(self) -> float:
        """Get API requests per minute (from Redis)"""
        from app.core.redis_client import cache_get
        # Implementation depends on how you track API metrics
        return 0.0
    
    async def _get_average_response_time(self) -> float:
        """Get average API response time (from Redis)"""
        return 0.0
    
    async def _get_error_rate(self) -> float:
        """Get API error rate percentage (from Redis)"""
        return 0.0