"""
Celery Tasks for Lead Generation
Background processing for lead scraping, enrichment, and scoring
"""

from celery import Task
from typing import List, Optional
from uuid import UUID
import asyncio

from app.core.celery_app import celery_app
from app.core.database import get_sync_session
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class LeadTask(Task):
    """Base task with retry and error handling"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3}
    retry_backoff = True
    retry_backoff_max = 60
    retry_jitter = True


@celery_app.task(base=LeadTask, bind=True, name="generate_leads_task")
def generate_leads_task(self, campaign_id: str):
    """
    Generate leads for a campaign
    This is the main orchestration task
    """
    logger.info(f"Starting lead generation for campaign {campaign_id}")
    
    try:
        # Import here to avoid circular imports
        from app.services.campaign_service import CampaignService
        from app.agents.graph import run_lead_generation_workflow
        
        # Get database session
        with get_sync_session() as db:
            campaign_service = CampaignService(db)
            campaign = campaign_service.get_campaign_by_id(UUID(campaign_id))
            
            if not campaign:
                logger.error(f"Campaign {campaign_id} not found")
                return {"status": "failed", "error": "Campaign not found"}
            
            # Run the LangGraph workflow
            result = run_lead_generation_workflow(
                campaign_id=str(campaign_id),
                query=campaign.query,
                sources=campaign.sources,
                target_count=campaign.target_leads_count
            )
            
            # Update campaign status
            if result.get("status") == "completed":
                campaign_service.update_campaign(UUID(campaign_id), {
                    "status": "completed",
                    "total_leads_found": result.get("total_leads", 0),
                    "unique_leads_added": result.get("unique_leads", 0),
                    "duplicate_leads_skipped": result.get("duplicates", 0)
                })
            
            logger.info(f"Lead generation completed for campaign {campaign_id}")
            return result
            
    except Exception as e:
        logger.error(f"Lead generation failed for campaign {campaign_id}: {e}")
        self.retry(exc=e)
        return {"status": "failed", "error": str(e)}


@celery_app.task(base=LeadTask, bind=True, name="enrich_leads_task")
def enrich_leads_task(self, lead_ids: List[str]):
    """
    Enrich leads using AI
    """
    logger.info(f"Starting enrichment for {len(lead_ids)} leads")
    
    try:
        from app.services.enrichment_service import EnrichmentService
        from app.core.database import get_sync_session
        
        enrichment_service = EnrichmentService()
        results = []
        
        with get_sync_session() as db:
            for lead_id in lead_ids:
                try:
                    # Get lead from database
                    from app.db.repositories.lead_repository import LeadRepository
                    repo = LeadRepository(db)
                    lead = repo.get_by_id(UUID(lead_id))
                    
                    if not lead:
                        results.append({"lead_id": lead_id, "status": "failed", "error": "Lead not found"})
                        continue
                    
                    # Enrich lead
                    enriched_data = enrichment_service.enrich_lead_sync(lead)
                    
                    # Update lead
                    repo.update(UUID(lead_id), {
                        "enriched_data": enriched_data,
                        "company_size": enriched_data.get("company_size"),
                        "funding_stage": enriched_data.get("funding_stage"),
                        "tech_stack": enriched_data.get("tech_stack", [])
                    })
                    
                    results.append({"lead_id": lead_id, "status": "success"})
                    
                except Exception as e:
                    logger.error(f"Enrichment failed for lead {lead_id}: {e}")
                    results.append({"lead_id": lead_id, "status": "failed", "error": str(e)})
        
        logger.info(f"Enrichment completed: {len([r for r in results if r['status'] == 'success'])} succeeded")
        return results
        
    except Exception as e:
        logger.error(f"Enrichment task failed: {e}")
        self.retry(exc=e)
        return {"status": "failed", "error": str(e)}


@celery_app.task(base=LeadTask, bind=True, name="score_leads_task")
def score_leads_task(self, lead_ids: List[str], recalculate: bool = True):
    """
    Score leads using algorithm
    """
    logger.info(f"Starting scoring for {len(lead_ids)} leads")
    
    try:
        from app.services.scoring_service import ScoringService
        from app.core.database import get_sync_session
        
        scoring_service = ScoringService()
        results = []
        
        with get_sync_session() as db:
            from app.db.repositories.lead_repository import LeadRepository
            repo = LeadRepository(db)
            
            for lead_id in lead_ids:
                try:
                    lead = repo.get_by_id(UUID(lead_id))
                    
                    if not lead:
                        results.append({"lead_id": lead_id, "status": "failed", "error": "Lead not found"})
                        continue
                    
                    # Calculate score
                    score = scoring_service.calculate_score_sync(lead)
                    
                    # Determine quality
                    if score >= 80:
                        quality = "hot"
                    elif score >= 60:
                        quality = "warm"
                    elif score >= 40:
                        quality = "cold"
                    else:
                        quality = "unqualified"
                    
                    # Update lead
                    repo.update(UUID(lead_id), {
                        "score": score,
                        "quality": quality
                    })
                    
                    results.append({"lead_id": lead_id, "status": "success", "score": score})
                    
                except Exception as e:
                    logger.error(f"Scoring failed for lead {lead_id}: {e}")
                    results.append({"lead_id": lead_id, "status": "failed", "error": str(e)})
        
        logger.info(f"Scoring completed: average score = {sum([r.get('score', 0) for r in results]) / len(results) if results else 0}")
        return results
        
    except Exception as e:
        logger.error(f"Scoring task failed: {e}")
        self.retry(exc=e)
        return {"status": "failed", "error": str(e)}


@celery_app.task(base=LeadTask, bind=True, name="deduplicate_leads_task")
def deduplicate_leads_task(self, campaign_id: str):
    """
    Find and mark duplicate leads in a campaign
    """
    logger.info(f"Starting deduplication for campaign {campaign_id}")
    
    try:
        from app.agents.lead_deduplicator import find_duplicates
        from app.core.database import get_sync_session
        
        with get_sync_session() as db:
            from app.db.repositories.lead_repository import LeadRepository
            repo = LeadRepository(db)
            
            # Get all leads in campaign
            leads = repo.get_by_campaign(UUID(campaign_id))
            
            duplicates_found = 0
            for lead in leads:
                # Find duplicates using vector similarity
                similar = find_duplicates(lead, leads)
                
                for dup in similar:
                    if dup.id != lead.id:
                        repo.update(dup.id, {"status": "duplicate"})
                        duplicates_found += 1
            
            logger.info(f"Deduplication completed: {duplicates_found} duplicates found")
            return {"campaign_id": campaign_id, "duplicates_found": duplicates_found}
            
    except Exception as e:
        logger.error(f"Deduplication task failed: {e}")
        self.retry(exc=e)
        return {"status": "failed", "error": str(e)}


@celery_app.task(base=LeadTask, bind=True, name="export_campaign_leads_task")
def export_campaign_leads_task(self, campaign_id: str, format: str, user_email: str):
    """
    Export leads from a campaign
    """
    logger.info(f"Starting export for campaign {campaign_id} to {format}")
    
    try:
        from app.services.export_service import ExportService
        from app.services.notification_service import NotificationService
        
        export_service = ExportService()
        notification_service = NotificationService()
        
        # Export leads
        download_url = export_service.export_campaign_sync(
            campaign_id=UUID(campaign_id),
            format=format
        )
        
        # Notify user
        notification_service.send_email(
            to_email=user_email,
            subject=f"Campaign Export Ready - {campaign_id}",
            body=f"Your export is ready. Download from: {download_url}"
        )
        
        logger.info(f"Export completed for campaign {campaign_id}")
        return {"campaign_id": campaign_id, "download_url": download_url}
        
    except Exception as e:
        logger.error(f"Export task failed: {e}")
        self.retry(exc=e)
        return {"status": "failed", "error": str(e)}


@celery_app.task(base=LeadTask, bind=True, name="sync_leads_to_vector_store")
def sync_leads_to_vector_store(self, lead_ids: List[str]):
    """
    Sync leads to vector store for semantic search
    """
    logger.info(f"Syncing {len(lead_ids)} leads to vector store")
    
    try:
        from app.vector_store.lead_index import LeadIndex
        
        index = LeadIndex()
        results = []
        
        for lead_id in lead_ids:
            try:
                index.add_lead_sync(UUID(lead_id))
                results.append({"lead_id": lead_id, "status": "success"})
            except Exception as e:
                logger.error(f"Sync failed for lead {lead_id}: {e}")
                results.append({"lead_id": lead_id, "status": "failed", "error": str(e)})
        
        logger.info(f"Vector store sync completed: {len([r for r in results if r['status'] == 'success'])} succeeded")
        return results
        
    except Exception as e:
        logger.error(f"Vector store sync task failed: {e}")
        self.retry(exc=e)
        return {"status": "failed", "error": str(e)}