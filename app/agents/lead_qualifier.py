"""
Lead Qualifier Agent
Determines if a lead is worth pursuing based on multiple criteria
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.core.logging import get_logger
from app.agents.base import BaseAgent, retry_on_failure
from app.tools.llm_failover import get_llm_client
from app.vector_store.rag_qualifier import get_rag_qualifier

logger = get_logger(__name__)


class LeadQualifierAgent(BaseAgent):
    """
    Agent responsible for qualifying leads
    Uses RAG (Retrieval-Augmented Generation) for intelligent qualification
    """
    
    def __init__(self):
        super().__init__(name="lead_qualifier", version="1.0.0")
        self.llm_client = get_llm_client()
        self.rag_qualifier = get_rag_qualifier()
    
    @retry_on_failure(max_retries=2)
    async def process(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Qualify a single lead
        """
        self.log_step("qualifying_lead", {"email": lead.get("email"), "score": lead.get("score")})
        
        try:
            # Get lead score (if not already present)
            score = lead.get("score", 50)
            threshold = 60
            
            # Use RAG for qualification
            if self.rag_qualifier:
                rag_result = await self.rag_qualifier.qualify_lead(
                    lead_data=lead,
                    campaign_context=None,
                    threshold=0.7,
                    top_k=5
                )
                
                is_qualified = rag_result.get("is_qualified", False)
                confidence = rag_result.get("confidence", "Medium")
                reasoning = rag_result.get("reasoning", [])
                rag_score = rag_result.get("score", score)
                
                # Blend with rule-based score
                final_score = int((score * 0.4) + (rag_score * 0.6))
                
            else:
                # Rule-based qualification
                is_qualified, reasoning, final_score = self._rule_based_qualification(
                    lead=lead,
                    threshold=threshold
                )
                confidence = "High" if final_score >= 80 else "Medium" if final_score >= 60 else "Low"
            
            # Determine next steps based on qualification
            if is_qualified:
                next_steps = self._get_next_steps(lead, final_score)
                status = "qualified"
            else:
                next_steps = ["Manual review recommended", "Add to nurture campaign"]
                status = "rejected"
            
            # Update lead with qualification data
            lead["is_qualified"] = is_qualified
            lead["qualification_score"] = final_score
            lead["qualification_confidence"] = confidence
            lead["qualification_reasoning"] = reasoning
            lead["qualification_next_steps"] = next_steps
            lead["status"] = status
            lead["qualified_at"] = datetime.utcnow().isoformat()
            
            self.logger.info(
                f"Lead {lead.get('email')} qualified: {is_qualified} "
                f"(score: {final_score}, confidence: {confidence})"
            )
            
            return lead
            
        except Exception as e:
            self.logger.error(f"Qualification failed for lead {lead.get('email')}: {e}")
            lead["is_qualified"] = False
            lead["qualification_error"] = str(e)
            lead["status"] = "qualification_failed"
            return lead
    
    async def qualify_batch(
        self,
        leads: List[Dict[str, Any]],
        threshold: int = 60,
        use_rag: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Qualify multiple leads in batch
        """
        self.logger.info(f"Qualifying batch of {len(leads)} leads with threshold {threshold}")
        
        if use_rag and self.rag_qualifier:
            # Use RAG for batch qualification
            return await self.process_batch(leads)
        else:
            # Use rule-based only
            qualified_leads = []
            for lead in leads:
                lead = await self.process(lead)
                qualified_leads.append(lead)
            return qualified_leads
    
    def _rule_based_qualification(
        self,
        lead: Dict[str, Any],
        threshold: int = 60
    ) -> Tuple[bool, List[str], int]:
        """
        Rule-based qualification logic
        Returns (is_qualified, reasoning, score)
        """
        score = lead.get("score", 0)
        email = lead.get("email", "")
        company = lead.get("company_name", "")
        job_title = lead.get("job_title", "")
        industry = lead.get("industry", "")
        
        reasoning = []
        points = 0
        
        # Score check
        if score >= threshold:
            points += 40
            reasoning.append(f"Score {score} meets threshold {threshold}")
        elif score >= 40:
            points += 20
            reasoning.append(f"Score {score} is below threshold but above 40")
        else:
            reasoning.append(f"Score {score} is too low")
        
        # Email check
        if email and "@" in email:
            points += 15
            reasoning.append("Valid email address present")
        else:
            reasoning.append("Missing or invalid email address")
        
        # Company check
        if company and len(company) > 2:
            points += 15
            reasoning.append(f"Company information present: {company}")
        else:
            reasoning.append("Missing company information")
        
        # Job title check
        if job_title:
            decision_keywords = ["ceo", "founder", "cto", "director", "vp", "head", "chief"]
            if any(keyword in job_title.lower() for keyword in decision_keywords):
                points += 20
                reasoning.append(f"Decision-maker job title detected: {job_title}")
            else:
                points += 10
                reasoning.append(f"Job title present: {job_title}")
        else:
            reasoning.append("Missing job title")
        
        # Industry check
        if industry:
            points += 10
            reasoning.append(f"Industry information present: {industry}")
        
        final_score = points
        is_qualified = final_score >= 60
        
        return is_qualified, reasoning, final_score
    
    def _get_next_steps(self, lead: Dict[str, Any], score: int) -> List[str]:
        """
        Generate recommended next steps based on qualification score
        """
        steps = []
        
        if score >= 80:
            steps = [
                "Send personalized outreach email within 24 hours",
                "Add to high-priority CRM list",
                "Schedule follow-up call in 3 days",
                "Share relevant case study"
            ]
        elif score >= 60:
            steps = [
                "Add to outreach sequence",
                "Research company for personalization",
                "Send initial contact email within 3 days",
                "Monitor for engagement signals"
            ]
        elif score >= 40:
            steps = [
                "Add to nurture campaign",
                "Engage with their content on LinkedIn",
                "Wait for buying signals"
            ]
        else:
            steps = [
                "Manual review required",
                "Check for missing data",
                "Consider adding to long-term nurture list"
            ]
        
        return steps
    
    async def _ai_qualify(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use AI for qualification (fallback when RAG is unavailable)
        """
        try:
            prompt = f"""
Qualify this lead for our business:

Lead Information:
- Company: {lead.get('company_name', 'Unknown')}
- Industry: {lead.get('industry', 'Unknown')}
- Job Title: {lead.get('job_title', 'Unknown')}
- Company Size: {lead.get('company_size', 'Unknown')}
- Score: {lead.get('score', 0)}/100

Return JSON with:
1. is_qualified: (true/false)
2. confidence: (High/Medium/Low)
3. reasoning: (list of reasons)
4. score: (0-100 qualification score)
"""
            response = await self.llm_client.complete_with_json(
                prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )
            
            return {
                "is_qualified": response.get("is_qualified", False),
                "confidence": response.get("confidence", "Medium"),
                "reasoning": response.get("reasoning", []),
                "score": min(100, max(0, response.get("score", 50)))
            }
            
        except Exception as e:
            self.logger.error(f"AI qualification failed: {e}")
            return {
                "is_qualified": lead.get("score", 0) >= 60,
                "confidence": "Low",
                "reasoning": ["AI qualification failed, using rule-based fallback"],
                "score": lead.get("score", 50)
            }


# Singleton instance
_qualifier_agent = None


def get_qualifier_agent() -> LeadQualifierAgent:
    """Get or create qualifier agent instance"""
    global _qualifier_agent
    if _qualifier_agent is None:
        _qualifier_agent = LeadQualifierAgent()
    return _qualifier_agent