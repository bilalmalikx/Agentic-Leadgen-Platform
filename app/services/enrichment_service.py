"""
Enrichment Service
AI-powered lead enrichment with LLM failover support
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
import json

from app.core.logging import get_logger
from app.core.config import settings
from app.tools.llm_failover import get_llm_client
from app.models.lead import Lead

logger = get_logger(__name__)


class EnrichmentService:
    """Service for AI-powered lead enrichment"""
    
    def __init__(self):
        self.llm_client = get_llm_client()
    
    async def enrich_lead(self, lead: Lead) -> Dict[str, Any]:
        """
        Enrich a single lead using AI
        Returns enriched data dictionary
        """
        try:
            # Build prompt for enrichment
            prompt = self._build_enrichment_prompt(lead)
            
            # Call LLM with failover
            response = await self.llm_client.complete_with_json(
                prompt=prompt,
                system_prompt="You are a lead enrichment expert. Extract structured data from the given information. Return ONLY valid JSON.",
                temperature=0.2
            )
            
            # Parse and validate response
            enriched_data = self._validate_enrichment_response(response)
            
            logger.info(f"Lead enriched: {lead.email}")
            return enriched_data
            
        except Exception as e:
            logger.error(f"Enrichment failed for lead {lead.email}: {e}")
            return self._get_default_enrichment()
    
    async def enrich_lead_sync(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous wrapper for enrichment
        (For Celery tasks)
        """
        return await self.enrich_lead(lead)
    
    async def enrich_batch(self, leads: List[Lead]) -> List[Dict[str, Any]]:
        """
        Enrich multiple leads in parallel
        """
        import asyncio
        tasks = [self.enrich_lead(lead) for lead in leads]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        enriched_data = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch enrichment failed for lead {leads[i].email}: {result}")
                enriched_data.append(self._get_default_enrichment())
            else:
                enriched_data.append(result)
        
        return enriched_data
    
    async def qualify_lead(self, lead: Lead) -> Dict[str, Any]:
        """
        Qualify lead using AI
        Returns qualification decision with reasoning
        """
        try:
            prompt = self._build_qualification_prompt(lead)
            
            response = await self.llm_client.complete_with_json(
                prompt=prompt,
                system_prompt="You are a lead qualification expert. Determine if this lead is worth pursuing. Return ONLY valid JSON.",
                temperature=0.3
            )
            
            qualification = {
                "is_qualified": response.get("is_qualified", False),
                "confidence": response.get("confidence", "Medium"),
                "reasoning": response.get("reasoning", []),
                "score": response.get("score", 50),
                "next_steps": response.get("next_steps", [])
            }
            
            return qualification
            
        except Exception as e:
            logger.error(f"Qualification failed for lead {lead.email}: {e}")
            return {
                "is_qualified": lead.score >= 60 if lead.score else False,
                "confidence": "Low",
                "reasoning": ["AI qualification failed, using rule-based fallback"],
                "score": lead.score or 50,
                "next_steps": ["Manual review recommended"]
            }
    
    def _build_enrichment_prompt(self, lead: Lead) -> str:
        """Build prompt for lead enrichment"""
        prompt = f"""Extract and enrich the following lead information:

Lead Information:
- Name: {lead.first_name or ''} {lead.last_name or ''}
- Email: {lead.email}
- Company: {lead.company_name or 'Unknown'}
- Job Title: {lead.job_title or 'Unknown'}
- Location: {lead.location or 'Unknown'}
- Source: {lead.source.value if lead.source else 'Unknown'}

Raw Data: {json.dumps(lead.raw_scraped_data or {}, indent=2)}

Extract the following fields:
1. company_size: (estimate from: 1-10, 11-50, 51-200, 201-500, 501-1000, 1000+)
2. funding_stage: (Bootstrapped, Seed, Series A, Series B, Series C+, Public)
3. tech_stack: (list of technologies this company likely uses)
4. industry: (specific industry like SaaS, Fintech, HealthTech, E-commerce, AI/ML, etc.)
5. estimated_revenue_million: (number in millions USD, estimate)
6. decision_maker_confidence: (High, Medium, Low)
7. key_technologies: (list of key technologies mentioned)

Return ONLY valid JSON with these fields."""
        
        return prompt
    
    def _build_qualification_prompt(self, lead: Lead) -> str:
        """Build prompt for lead qualification"""
        prompt = f"""Qualify this lead for our business:

Lead Information:
- Company: {lead.company_name or 'Unknown'}
- Industry: {lead.industry or 'Unknown'}
- Job Title: {lead.job_title or 'Unknown'}
- Company Size: {lead.company_size or 'Unknown'}
- Funding Stage: {lead.funding_stage or 'Unknown'}
- Tech Stack: {lead.tech_stack or []}
- Score: {lead.score or 0}

Our Ideal Customer Profile (ICP):
- Industry: SaaS, AI/ML, Fintech, HealthTech
- Company Size: 11-500 employees
- Decision Maker: CTO, CEO, Founder, VP Engineering, Head of Product
- Tech Stack: Modern cloud technologies (AWS, GCP, Azure, Kubernetes, etc.)

Return JSON with:
1. is_qualified: (true/false)
2. confidence: (High/Medium/Low)
3. reasoning: (list of reasons)
4. score: (0-100 qualification score)
5. next_steps: (list of recommended actions)"""
        
        return prompt
    
    def _validate_enrichment_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize enrichment response"""
        defaults = {
            "company_size": "Unknown",
            "funding_stage": "Unknown",
            "tech_stack": [],
            "industry": "Unknown",
            "estimated_revenue_million": None,
            "decision_maker_confidence": "Medium",
            "key_technologies": []
        }
        
        for key, default in defaults.items():
            if key not in response or response[key] is None:
                response[key] = default
        
        # Ensure tech_stack is a list
        if not isinstance(response.get("tech_stack"), list):
            response["tech_stack"] = []
        
        # Ensure key_technologies is a list
        if not isinstance(response.get("key_technologies"), list):
            response["key_technologies"] = []
        
        return response
    
    def _get_default_enrichment(self) -> Dict[str, Any]:
        """Get default enrichment data when AI fails"""
        return {
            "company_size": "Unknown",
            "funding_stage": "Unknown",
            "tech_stack": [],
            "industry": "Unknown",
            "estimated_revenue_million": None,
            "decision_maker_confidence": "Low",
            "key_technologies": [],
            "enrichment_failed": True
        }