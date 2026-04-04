"""
Celery Tasks for Lead Enrichment
Background jobs for AI-powered lead enrichment
"""

from celery import Task
from typing import List, Dict, Any, Optional
from uuid import UUID
import asyncio

from app.core.celery_app import celery_app
from app.core.database import get_sync_session
from app.core.logging import get_logger

logger = get_logger(__name__)


class EnrichmentTask(Task):
    """Base enrichment task with retry"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 3}
    retry_backoff = True


@celery_app.task(base=EnrichmentTask, bind=True, name="enrich_single_lead_task")
def enrich_single_lead_task(self, lead_id: str):
    """
    Enrich a single lead using AI
    """
    logger.info(f"Starting enrichment for lead {lead_id}")
    
    try:
        from app.services.enrichment_service import EnrichmentService
        from app.db.repositories.lead_repository import LeadRepository
        
        with get_sync_session() as db:
            repo = LeadRepository(db)
            lead = repo.get_by_id(UUID(lead_id))
            
            if not lead:
                return {"lead_id": lead_id, "error": "Lead not found"}
            
            enrichment_service = EnrichmentService()
            
            # Run enrichment (sync wrapper for Celery)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            enriched_data = loop.run_until_complete(
                enrichment_service.enrich_lead(lead)
            )
            loop.close()
            
            # Update lead with enriched data
            repo.update(UUID(lead_id), {
                "enriched_data": enriched_data,
                "company_size": enriched_data.get("company_size"),
                "funding_stage": enriched_data.get("funding_stage"),
                "tech_stack": enriched_data.get("tech_stack", [])
            })
            
            logger.info(f"Enrichment completed for lead {lead_id}")
            return {"lead_id": lead_id, "status": "success", "enriched_data": enriched_data}
            
    except Exception as e:
        logger.error(f"Enrichment failed for lead {lead_id}: {e}")
        self.retry(exc=e)
        return {"lead_id": lead_id, "error": str(e)}


@celery_app.task(base=EnrichmentTask, bind=True, name="enrich_batch_leads_task")
def enrich_batch_leads_task(self, lead_ids: List[str], batch_size: int = 10):
    """
    Enrich multiple leads in batch
    """
    logger.info(f"Starting batch enrichment for {len(lead_ids)} leads")
    
    try:
        results = []
        successful = 0
        failed = 0
        
        for i in range(0, len(lead_ids), batch_size):
            batch = lead_ids[i:i + batch_size]
            
            for lead_id in batch:
                result = enrich_single_lead_task.delay(lead_id).get(timeout=120)
                results.append(result)
                if result.get("status") == "success":
                    successful += 1
                else:
                    failed += 1
        
        logger.info(f"Batch enrichment completed: {successful} succeeded, {failed} failed")
        return {
            "total": len(lead_ids),
            "successful": successful,
            "failed": failed,
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Batch enrichment failed: {e}")
        self.retry(exc=e)
        return {"error": str(e)}


@celery_app.task(base=EnrichmentTask, bind=True, name="refresh_lead_embeddings")
def refresh_lead_embeddings(self, campaign_id: Optional[str] = None):
    """
    Refresh embeddings for leads in vector store
    """
    logger.info(f"Refreshing lead embeddings for campaign {campaign_id}")
    
    try:
        from app.vector_store.lead_index import get_lead_index
        from app.db.repositories.lead_repository import LeadRepository
        
        with get_sync_session() as db:
            repo = LeadRepository(db)
            
            if campaign_id:
                leads, _ = repo.get_by_campaign(UUID(campaign_id), limit=10000)
            else:
                # Get all leads (limit to 10000 for performance)
                leads, _ = repo.get_all(limit=10000)
            
            index = get_lead_index()
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            successful = 0
            for lead in leads:
                try:
                    loop.run_until_complete(
                        index.add_lead(lead.id, {
                            "email": lead.email,
                            "company_name": lead.company_name,
                            "job_title": lead.job_title,
                            "industry": lead.industry,
                            "score": lead.score
                        })
                    )
                    successful += 1
                except Exception as e:
                    logger.error(f"Failed to refresh embedding for lead {lead.id}: {e}")
            
            loop.close()
            
            logger.info(f"Embedding refresh completed: {successful}/{len(leads)} leads updated")
            return {"total": len(leads), "updated": successful}
            
    except Exception as e:
        logger.error(f"Embedding refresh failed: {e}")
        return {"error": str(e)}


@celery_app.task(base=EnrichmentTask, bind=True, name="enrich_campaign_leads_task")
def enrich_campaign_leads_task(self, campaign_id: str):
    """
    Enrich all leads in a campaign
    """
    logger.info(f"Starting enrichment for all leads in campaign {campaign_id}")
    
    try:
        from app.db.repositories.lead_repository import LeadRepository
        
        with get_sync_session() as db:
            repo = LeadRepository(db)
            leads, total = repo.get_by_campaign(UUID(campaign_id), limit=10000)
            
            lead_ids = [str(lead.id) for lead in leads]
            
            # Trigger batch enrichment
            result = enrich_batch_leads_task.delay(lead_ids).get(timeout=3600)
            
            logger.info(f"Campaign {campaign_id} enrichment completed")
            return {
                "campaign_id": campaign_id,
                "total_leads": total,
                "enriched": result.get("successful", 0)
            }
            
    except Exception as e:
        logger.error(f"Campaign enrichment failed: {e}")
        return {"campaign_id": campaign_id, "error": str(e)}