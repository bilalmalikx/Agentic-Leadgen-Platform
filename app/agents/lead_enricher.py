"""
Lead Enricher Agent
AI-powered enrichment using LLM with failover support
"""

from typing import List, Dict, Any, Optional
import asyncio
import json

from app.core.logging import get_logger
from app.core.config import settings
from app.tools.llm_failover import LLMClientWithFailover

logger = get_logger(__name__)


class LeadEnricherAgent:
    """
    Agent that enriches lead data using AI
    Adds company info, tech stack, funding details, etc.
    """
    
    def __init__(self):
        self.llm_client = LLMClientWithFailover()
    
    async def enrich_batch(
        self,
        leads: List[Dict[str, Any]],
        batch_size: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Enrich multiple leads in parallel
        """
        logger.info(f"Enriching {len(leads)} leads")
        
        enriched_leads = []
        
        # Process in batches
        for i in range(0, len(leads), batch_size):
            batch = leads[i:i + batch_size]
            batch_tasks = [self._enrich_single_lead(lead) for lead in batch]
            batch_results = await asyncio.gather(*batch_tasks)
            enriched_leads.extend(batch_results)
        
        return enriched_leads
    
    async def _enrich_single_lead(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich a single lead using LLM
        """
        try:
            # Prepare prompt for enrichment
            prompt = self._build_enrichment_prompt(lead)
            
            # Call LLM with failover
            response = await self.llm_client.complete(
                prompt=prompt,
                system_prompt="You are a lead enrichment expert. Extract structured data from the given information.",
                temperature=0.2,
                max_tokens=500
            )
            
            # Parse LLM response
            enriched_data = self._parse_enrichment_response(response)
            
            # Merge with original lead
            lead["enriched_data"] = enriched_data
            lead["company_size"] = enriched_data.get("company_size")
            lead["funding_stage"] = enriched_data.get("funding_stage")
            lead["tech_stack"] = enriched_data.get("tech_stack", [])
            
            logger.debug(f"Enriched lead: {lead.get('email')}")
            
        except Exception as e:
            logger.error(f"Enrichment failed for {lead.get('email')}: {e}")
            lead["enriched_data"] = {}
            lead["enrichment_error"] = str(e)
        
        return lead
    
    def _build_enrichment_prompt(self, lead: Dict[str, Any]) -> str:
        """
        Build prompt for LLM enrichment
        """
        prompt = f"""Extract and enrich the following lead information:

Lead Information:
- Name: {lead.get('first_name', '')} {lead.get('last_name', '')}
- Company: {lead.get('company_name', 'Unknown')}
- Job Title: {lead.get('job_title', 'Unknown')}
- Location: {lead.get('location', 'Unknown')}
- Source: {lead.get('source', 'Unknown')}

Raw Data: {json.dumps(lead.get('raw_data', {}), indent=2)}

Please extract/enrich the following fields in JSON format:
1. company_size: (estimate from 1-10, 11-50, 51-200, 201-500, 501-1000, 1000+)
2. funding_stage: (Bootstrapped, Seed, Series A, Series B, Series C+, Public)
3. tech_stack: (list of technologies this company likely uses)
4. industry: (specific industry like SaaS, Fintech, HealthTech, E-commerce, etc.)
5. estimated_revenue: (in millions USD)
6. key_technologies: (list of key technologies mentioned)
7. decision_maker_confidence: (High, Medium, Low - based on job title)

Return ONLY valid JSON, no other text.
"""
        return prompt
    
    def _parse_enrichment_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured data
        """
        try:
            # Try to extract JSON from response
            response = response.strip()
            
            # Remove markdown code blocks if present
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            data = json.loads(response)
            
            # Ensure required fields
            defaults = {
                "company_size": "Unknown",
                "funding_stage": "Unknown",
                "tech_stack": [],
                "industry": "Unknown",
                "estimated_revenue": None,
                "key_technologies": [],
                "decision_maker_confidence": "Medium"
            }
            
            for key, default in defaults.items():
                if key not in data:
                    data[key] = default
            
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse enrichment response: {e}")
            return {
                "company_size": "Unknown",
                "funding_stage": "Unknown",
                "tech_stack": [],
                "industry": "Unknown",
                "raw_response": response[:500]
            }
    
    async def enrich_lead_sync(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous wrapper for enrichment
        (For Celery tasks)
        """
        result = await self._enrich_single_lead(lead)
        return result.get("enriched_data", {})