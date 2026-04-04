"""
MCP Tools - Individual tool implementations
Each tool is a function that can be called by AI assistants
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime
import json

from app.core.logging import get_logger
from app.core.database import get_sync_session
from app.db.repositories.lead_repository import LeadRepository
from app.db.repositories.campaign_repository import CampaignRepository
from app.services.enrichment_service import EnrichmentService
from app.services.scoring_service import ScoringService
from app.services.export_service import ExportService

logger = get_logger(__name__)


# ============================================
# Tool 1: Scrape LinkedIn
# ============================================

async def scrape_linkedin_tool(query: str, limit: int = 50) -> Dict[str, Any]:
    """
    Scrape LinkedIn profiles based on search query
    
    Args:
        query: Search query (e.g., "CTO at AI startup")
        limit: Maximum number of profiles to scrape
    
    Returns:
        Dictionary with scraped leads
    """
    logger.info(f"MCP Tool: scrape_linkedin called with query='{query}', limit={limit}")
    
    try:
        from app.scrapers.linkedin import LinkedInScraper
        
        scraper = LinkedInScraper()
        results = await scraper.scrape(query=query, limit=limit)
        
        return {
            "success": True,
            "query": query,
            "limit": limit,
            "leads_found": len(results),
            "leads": results[:10],  # Return first 10 for preview
            "message": f"Successfully scraped {len(results)} leads from LinkedIn"
        }
        
    except Exception as e:
        logger.error(f"LinkedIn scrape tool failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to scrape LinkedIn: {str(e)}"
        }


# ============================================
# Tool 2: Enrich Lead
# ============================================

async def enrich_lead_tool(
    email: str,
    company_name: Optional[str] = None,
    job_title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enrich lead data using AI
    
    Args:
        email: Lead email address
        company_name: Company name (optional)
        job_title: Job title (optional)
    
    Returns:
        Dictionary with enriched data
    """
    logger.info(f"MCP Tool: enrich_lead called for email='{email}'")
    
    try:
        # Try to get existing lead from database
        with get_sync_session() as db:
            lead_repo = LeadRepository(db)
            lead = lead_repo.get_by_email(email)
            
            if lead:
                # Lead exists, use its data
                lead_data = {
                    "email": lead.email,
                    "company_name": lead.company_name,
                    "job_title": lead.job_title,
                    "industry": lead.industry,
                    "location": lead.location
                }
            else:
                # Create temporary lead data
                lead_data = {
                    "email": email,
                    "company_name": company_name,
                    "job_title": job_title
                }
        
        # Run enrichment
        enrichment_service = EnrichmentService()
        enriched_data = await enrichment_service.enrich_lead_sync(lead_data)
        
        return {
            "success": True,
            "email": email,
            "enriched_data": enriched_data,
            "message": f"Successfully enriched lead data for {email}"
        }
        
    except Exception as e:
        logger.error(f"Enrich lead tool failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to enrich lead: {str(e)}"
        }


# ============================================
# Tool 3: Score Lead
# ============================================

async def score_lead_tool(
    lead_id: Optional[str] = None,
    email: Optional[str] = None
) -> Dict[str, Any]:
    """
    Score a lead based on multiple criteria
    
    Args:
        lead_id: Lead ID (UUID)
        email: Lead email (if lead_id not provided)
    
    Returns:
        Dictionary with score and breakdown
    """
    logger.info(f"MCP Tool: score_lead called for lead_id='{lead_id}', email='{email}'")
    
    try:
        with get_sync_session() as db:
            lead_repo = LeadRepository(db)
            
            if lead_id:
                lead = lead_repo.get_by_id(UUID(lead_id))
            elif email:
                lead = lead_repo.get_by_email(email)
            else:
                return {
                    "success": False,
                    "error": "Either lead_id or email is required",
                    "message": "Please provide lead_id or email"
                }
            
            if not lead:
                return {
                    "success": False,
                    "error": "Lead not found",
                    "message": f"No lead found with provided identifier"
                }
            
            # Calculate score
            scoring_service = ScoringService()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            score = loop.run_until_complete(scoring_service.calculate_score(lead))
            loop.close()
            
            # Get score breakdown
            breakdown = scoring_service.get_score_breakdown(lead)
            
            return {
                "success": True,
                "lead_id": str(lead.id),
                "email": lead.email,
                "score": score,
                "breakdown": breakdown,
                "message": f"Lead scored: {score}/100"
            }
        
    except Exception as e:
        logger.error(f"Score lead tool failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to score lead: {str(e)}"
        }


# ============================================
# Tool 4: Search Leads
# ============================================

async def search_leads_tool(
    query: str,
    status: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """
    Search leads in the database
    
    Args:
        query: Search query (searches in name, email, company)
        status: Filter by status (new, contacted, qualified, converted, rejected)
        limit: Maximum number of results
    
    Returns:
        Dictionary with search results
    """
    logger.info(f"MCP Tool: search_leads called with query='{query}', status='{status}'")
    
    try:
        with get_sync_session() as db:
            lead_repo = LeadRepository(db)
            
            # Build search filters
            filters = {"query": query}
            if status:
                filters["status"] = status
            
            leads, total = lead_repo.search_by_keyword(
                keyword=query,
                offset=0,
                limit=limit
            )
            
            # Format results
            results = []
            for lead in leads:
                results.append({
                    "id": str(lead.id),
                    "email": lead.email,
                    "full_name": lead.full_name,
                    "company_name": lead.company_name,
                    "job_title": lead.job_title,
                    "score": lead.score,
                    "status": lead.status.value if lead.status else None,
                    "quality": lead.quality.value if lead.quality else None,
                    "created_at": lead.created_at.isoformat() if lead.created_at else None
                })
            
            return {
                "success": True,
                "query": query,
                "total": total,
                "limit": limit,
                "results": results,
                "message": f"Found {total} leads matching '{query}'"
            }
        
    except Exception as e:
        logger.error(f"Search leads tool failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to search leads: {str(e)}"
        }


# ============================================
# Tool 5: Get Campaign Status
# ============================================

async def get_campaign_status_tool(campaign_id: str) -> Dict[str, Any]:
    """
    Get status and progress of a campaign
    
    Args:
        campaign_id: Campaign ID (UUID)
    
    Returns:
        Dictionary with campaign status and progress
    """
    logger.info(f"MCP Tool: get_campaign_status called for campaign_id='{campaign_id}'")
    
    try:
        with get_sync_session() as db:
            campaign_repo = CampaignRepository(db)
            campaign = campaign_repo.get_by_id(UUID(campaign_id))
            
            if not campaign:
                return {
                    "success": False,
                    "error": "Campaign not found",
                    "message": f"No campaign found with ID {campaign_id}"
                }
            
            # Get lead stats
            from app.db.repositories.lead_repository import LeadRepository
            lead_repo = LeadRepository(db)
            lead_stats = await lead_repo.get_stats_by_campaign(UUID(campaign_id))
            
            return {
                "success": True,
                "campaign_id": str(campaign.id),
                "name": campaign.name,
                "status": campaign.status.value if campaign.status else None,
                "priority": campaign.priority.value if campaign.priority else None,
                "progress_percentage": campaign.progress_percentage,
                "target_leads": campaign.target_leads_count,
                "total_leads_found": campaign.total_leads_found,
                "unique_leads_added": campaign.unique_leads_added,
                "lead_stats": lead_stats,
                "started_at": campaign.started_at.isoformat() if campaign.started_at else None,
                "completed_at": campaign.completed_at.isoformat() if campaign.completed_at else None,
                "message": f"Campaign '{campaign.name}' is {campaign.status.value} ({campaign.progress_percentage}% complete)"
            }
        
    except Exception as e:
        logger.error(f"Get campaign status tool failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to get campaign status: {str(e)}"
        }


# ============================================
# Tool 6: Export Leads
# ============================================

async def export_leads_tool(
    campaign_id: str,
    format: str = "csv"
) -> Dict[str, Any]:
    """
    Export leads to CSV or JSON format
    
    Args:
        campaign_id: Campaign ID to export from
        format: Export format (csv or json)
    
    Returns:
        Dictionary with download URL
    """
    logger.info(f"MCP Tool: export_leads called for campaign_id='{campaign_id}', format='{format}'")
    
    try:
        with get_sync_session() as db:
            campaign_repo = CampaignRepository(db)
            campaign = campaign_repo.get_by_id(UUID(campaign_id))
            
            if not campaign:
                return {
                    "success": False,
                    "error": "Campaign not found",
                    "message": f"No campaign found with ID {campaign_id}"
                }
            
            # Run export
            export_service = ExportService()
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                export_service.export_campaign_sync(
                    campaign_id=UUID(campaign_id),
                    format=format
                )
            )
            loop.close()
            
            return {
                "success": True,
                "campaign_id": campaign_id,
                "campaign_name": campaign.name,
                "format": format,
                "download_url": result,
                "message": f"Export ready! Download from: {result}"
            }
        
    except Exception as e:
        logger.error(f"Export leads tool failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to export leads: {str(e)}"
        }


# ============================================
# Tool 7: Create Campaign (Bonus)
# ============================================

async def create_campaign_tool(
    name: str,
    query: str,
    sources: List[str],
    target_leads: int = 100
) -> Dict[str, Any]:
    """
    Create a new lead generation campaign
    
    Args:
        name: Campaign name
        query: Search query
        sources: List of sources (linkedin, twitter, crunchbase)
        target_leads: Target number of leads
    
    Returns:
        Dictionary with created campaign info
    """
    logger.info(f"MCP Tool: create_campaign called with name='{name}', query='{query}'")
    
    try:
        from app.services.campaign_service import CampaignService
        
        campaign_data = {
            "name": name,
            "query": query,
            "sources": sources,
            "target_leads_count": target_leads,
            "status": "draft"
        }
        
        # For demo purposes, create with default user
        # In production, would need user context
        with get_sync_session() as db:
            campaign_service = CampaignService(db)
            # Use a default user ID (in production, get from auth)
            default_user_id = UUID("00000000-0000-0000-0000-000000000001")
            campaign = await campaign_service.create_campaign(campaign_data, default_user_id)
            
            return {
                "success": True,
                "campaign_id": str(campaign.id),
                "name": campaign.name,
                "query": campaign.query,
                "sources": campaign.sources,
                "target_leads": campaign.target_leads_count,
                "message": f"Campaign '{name}' created successfully"
            }
        
    except Exception as e:
        logger.error(f"Create campaign tool failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to create campaign: {str(e)}"
        }