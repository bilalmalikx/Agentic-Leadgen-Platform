"""
Lead Scorer Agent
Scores leads based on multiple criteria using AI and rule-based algorithms
"""

from typing import List, Dict, Any, Optional, Tuple
import re
import asyncio
from datetime import datetime

from app.core.logging import get_logger
from app.core.constants import SCORING_WEIGHTS, JOB_TITLE_PRIORITY
from app.agents.base import BaseAgent, retry_on_failure
from app.tools.llm_failover import get_llm_client

logger = get_logger(__name__)


class LeadScorerAgent(BaseAgent):
    """
    Agent responsible for scoring leads
    Combines rule-based scoring with AI-powered scoring
    """
    
    def __init__(self):
        super().__init__(name="lead_scorer", version="1.0.0")
        self.weights = SCORING_WEIGHTS
        self.llm_client = get_llm_client()
    
    @retry_on_failure(max_retries=2)
    async def process(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Score a single lead
        """
        self.log_step("scoring_lead", {"email": lead.get("email")})
        
        try:
            # Calculate individual component scores
            scores = {
                "job_title_match": self._score_job_title(lead),
                "company_relevance": self._score_company_relevance(lead),
                "social_activity": self._score_social_activity(lead),
                "company_size": self._score_company_size(lead),
                "location_match": self._score_location(lead)
            }
            
            # Calculate weighted total
            total_score = 0
            for component, score in scores.items():
                weight = self.weights.get(component, 0)
                total_score += score * weight
            
            final_score = int(round(total_score))
            final_score = max(0, min(100, final_score))
            
            # If AI scoring is enabled, enhance the score
            if self.llm_client:
                ai_score = await self._ai_score_lead(lead)
                # Blend AI score with rule-based score (70% rule, 30% AI)
                final_score = int((final_score * 0.7) + (ai_score * 0.3))
                final_score = max(0, min(100, final_score))
            
            # Determine quality category
            if final_score >= 80:
                quality = "hot"
            elif final_score >= 60:
                quality = "warm"
            elif final_score >= 40:
                quality = "cold"
            else:
                quality = "unqualified"
            
            lead["score"] = final_score
            lead["quality"] = quality
            lead["score_breakdown"] = scores
            lead["scored_at"] = datetime.utcnow().isoformat()
            
            self.logger.info(f"Lead {lead.get('email')} scored: {final_score} ({quality})")
            return lead
            
        except Exception as e:
            self.logger.error(f"Scoring failed for lead {lead.get('email')}: {e}")
            lead["score"] = 0
            lead["quality"] = "unqualified"
            lead["score_error"] = str(e)
            return lead
    
    async def score_batch(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Score multiple leads in batch
        """
        self.logger.info(f"Scoring batch of {len(leads)} leads")
        return await self.process_batch(leads)
    
    def _score_job_title(self, lead: Dict[str, Any]) -> float:
        """
        Score based on job title (0-1)
        Higher score for decision-maker titles
        """
        job_title = (lead.get("job_title") or "").lower()
        
        if not job_title:
            return 0.3
        
        # Check for exact matches in priority map
        for title, priority in JOB_TITLE_PRIORITY.items():
            if title in job_title:
                return priority / 100.0
        
        # Decision-maker patterns
        decision_patterns = [
            "head of", "director of", "vp of", "vice president",
            "chief", "c[toefo]o", "founder", "co-founder",
            "principal", "lead", "manager", "senior"
        ]
        
        for pattern in decision_patterns:
            if re.search(pattern, job_title):
                return 0.8
        
        # Technical roles
        tech_patterns = ["engineer", "developer", "architect", "scientist"]
        for pattern in tech_patterns:
            if re.search(pattern, job_title):
                return 0.6
        
        return 0.4
    
    def _score_company_relevance(self, lead: Dict[str, Any]) -> float:
        """Score based on company relevance to target industries"""
        industry = (lead.get("industry") or "").lower()
        company_name = (lead.get("company_name") or "").lower()
        
        target_industries = [
            "saas", "software", "ai", "machine learning", "ml",
            "fintech", "healthtech", "biotech", "cloud", "cybersecurity",
            "e-commerce", "marketplace", "adtech", "martech"
        ]
        
        for keyword in target_industries:
            if keyword in industry or keyword in company_name:
                return 1.0
        
        return 0.5
    
    def _score_social_activity(self, lead: Dict[str, Any]) -> float:
        """Score based on social media presence"""
        score = 0.3
        
        if lead.get("linkedin_url"):
            score += 0.3
        if lead.get("twitter_handle"):
            score += 0.2
        
        raw_data = lead.get("raw_data") or lead.get("raw_scraped_data") or {}
        
        connections = raw_data.get("connections", 0)
        if connections > 500:
            score += 0.2
        elif connections > 100:
            score += 0.1
        
        followers = raw_data.get("followers", 0)
        if followers > 5000:
            score += 0.2
        elif followers > 1000:
            score += 0.1
        
        return min(1.0, score)
    
    def _score_company_size(self, lead: Dict[str, Any]) -> float:
        """Score based on company size"""
        company_size = (lead.get("company_size") or "").lower()
        
        size_scores = {
            "1-10": 0.4,
            "11-50": 1.0,
            "51-200": 1.0,
            "201-500": 0.8,
            "501-1000": 0.5,
            "1000+": 0.3
        }
        
        for size, score in size_scores.items():
            if size in company_size:
                return score
        
        return 0.5
    
    def _score_location(self, lead: Dict[str, Any]) -> float:
        """Score based on location relevance"""
        location = (lead.get("location") or "").lower()
        
        high_value_locations = [
            "san francisco", "new york", "boston", "seattle", "austin",
            "london", "berlin", "bangalore", "singapore", "sydney",
            "toronto", "tel aviv", "amsterdam", "paris"
        ]
        
        for hub in high_value_locations:
            if hub in location:
                return 1.0
        
        if "united states" in location or "usa" in location:
            return 0.8
        if "remote" in location:
            return 0.6
        
        return 0.5
    
    async def _ai_score_lead(self, lead: Dict[str, Any]) -> int:
        """
        Use AI to score lead (0-100)
        """
        try:
            prompt = f"""
Score this lead from 0-100 based on sales potential:

Lead Information:
- Company: {lead.get('company_name', 'Unknown')}
- Industry: {lead.get('industry', 'Unknown')}
- Job Title: {lead.get('job_title', 'Unknown')}
- Company Size: {lead.get('company_size', 'Unknown')}
- Location: {lead.get('location', 'Unknown')}

Consider:
1. Decision-making authority (30%)
2. Company growth potential (25%)
3. Industry relevance (25%)
4. Budget availability (20%)

Return ONLY a number between 0-100.
"""
            response = await self.llm_client.complete(
                prompt=prompt,
                temperature=0.1,
                max_tokens=10
            )
            
            # Extract number from response
            numbers = re.findall(r'\d+', response)
            if numbers:
                score = int(numbers[0])
                return min(100, max(0, score))
            
            return 50
            
        except Exception as e:
            self.logger.error(f"AI scoring failed: {e}")
            return 50
    
    def get_score_breakdown(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed score breakdown for reporting
        """
        scores = {
            "job_title_match": self._score_job_title(lead),
            "company_relevance": self._score_company_relevance(lead),
            "social_activity": self._score_social_activity(lead),
            "company_size": self._score_company_size(lead),
            "location_match": self._score_location(lead)
        }
        
        weighted_scores = {}
        total = 0
        
        for component, score in scores.items():
            weight = self.weights.get(component, 0)
            weighted = score * weight * 100
            weighted_scores[component] = {
                "raw_score": round(score, 2),
                "weight": weight,
                "weighted_score": round(weighted, 2)
            }
            total += weighted
        
        return {
            "total_score": int(round(total)),
            "components": weighted_scores,
            "weights_used": self.weights
        }


# Singleton instance
_scorer_agent = None


def get_scorer_agent() -> LeadScorerAgent:
    """Get or create scorer agent instance"""
    global _scorer_agent
    if _scorer_agent is None:
        _scorer_agent = LeadScorerAgent()
    return _scorer_agent