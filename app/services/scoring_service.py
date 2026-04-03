"""
Scoring Service
Lead scoring algorithms and weight-based calculation
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
import re

from app.core.logging import get_logger
from app.core.constants import SCORING_WEIGHTS, JOB_TITLE_PRIORITY
from app.models.lead import Lead

logger = get_logger(__name__)


class ScoringService:
    """Service for lead scoring calculations"""
    
    def __init__(self):
        self.weights = SCORING_WEIGHTS
    
    async def calculate_score(self, lead: Lead) -> int:
        """
        Calculate lead score based on multiple factors
        Returns score from 0-100
        """
        scores = {}
        
        # Calculate individual component scores
        scores["job_title_match"] = self._score_job_title(lead)
        scores["company_relevance"] = self._score_company_relevance(lead)
        scores["social_activity"] = self._score_social_activity(lead)
        scores["company_size"] = self._score_company_size(lead)
        scores["location_match"] = self._score_location(lead)
        
        # Calculate weighted total
        total_score = 0
        for component, score in scores.items():
            weight = self.weights.get(component, 0)
            total_score += score * weight
        
        # Round to integer
        final_score = int(round(total_score))
        
        # Ensure within 0-100 range
        final_score = max(0, min(100, final_score))
        
        logger.debug(f"Score calculated for {lead.email}: {final_score} (components: {scores})")
        
        return final_score
    
    async def calculate_score_sync(self, lead: Dict[str, Any]) -> int:
        """Synchronous wrapper for scoring (for Celery tasks)"""
        # Convert dict to object-like access
        class LeadObj:
            pass
        
        lead_obj = LeadObj()
        for key, value in lead.items():
            setattr(lead_obj, key, value)
        
        return await self.calculate_score(lead_obj)
    
    async def score_batch(self, leads: List[Lead]) -> List[int]:
        """
        Score multiple leads in parallel
        """
        import asyncio
        tasks = [self.calculate_score(lead) for lead in leads]
        scores = await asyncio.gather(*tasks)
        return scores
    
    def _score_job_title(self, lead: Lead) -> float:
        """
        Score based on job title (0-1)
        Higher score for decision-maker titles
        """
        job_title = (lead.job_title or "").lower()
        
        if not job_title:
            return 0.3  # Default score for unknown
        
        # Check for exact matches in priority map
        for title, priority in JOB_TITLE_PRIORITY.items():
            if title in job_title:
                return priority / 100.0  # Normalize to 0-1
        
        # Pattern matching for common decision-maker indicators
        decision_maker_patterns = [
            r"head of", r"director of", r"vp of", r"vice president",
            r"chief", r"c[toef]o", r"founder", r"co-founder",
            r"principal", r"lead", r"manager"
        ]
        
        for pattern in decision_maker_patterns:
            if re.search(pattern, job_title):
                return 0.8
        
        # Technical roles
        technical_patterns = [
            r"engineer", r"developer", r"architect", r"scientist"
        ]
        
        for pattern in technical_patterns:
            if re.search(pattern, job_title):
                return 0.6
        
        return 0.4  # Default for other roles
    
    def _score_company_relevance(self, lead: Lead) -> float:
        """
        Score based on company relevance to target industries
        """
        industry = (lead.industry or "").lower()
        company_name = (lead.company_name or "").lower()
        
        # Target industries (high relevance)
        target_industries = [
            "saas", "software", "ai", "machine learning", "ml",
            "fintech", "healthtech", "biotech", "cloud", "cybersecurity",
            "e-commerce", "marketplace", "adtech", "martech"
        ]
        
        score = 0.5  # Default
        
        for industry_keyword in target_industries:
            if industry_keyword in industry or industry_keyword in company_name:
                score = 1.0
                break
        
        return score
    
    def _score_social_activity(self, lead: Lead) -> float:
        """
        Score based on social media presence and engagement
        """
        score = 0.3  # Default low score
        
        # Check for LinkedIn presence
        if lead.linkedin_url:
            score += 0.3
        
        # Check for Twitter presence
        if lead.twitter_handle:
            score += 0.2
        
        # Check raw data for social metrics
        raw_data = lead.raw_scraped_data or {}
        
        # LinkedIn followers/connections
        connections = raw_data.get("connections", 0)
        if connections > 500:
            score += 0.2
        elif connections > 100:
            score += 0.1
        
        # Twitter followers
        followers = raw_data.get("followers", 0)
        if followers > 5000:
            score += 0.2
        elif followers > 1000:
            score += 0.1
        
        return min(1.0, score)
    
    def _score_company_size(self, lead: Lead) -> float:
        """
        Score based on company size
        Ideal size: 11-500 employees (startups to mid-market)
        """
        company_size = (lead.company_size or "").lower()
        
        # Ideal size mapping
        size_scores = {
            "1-10": 0.4,      # Too small
            "11-50": 1.0,      # Ideal
            "51-200": 1.0,     # Ideal
            "201-500": 0.8,    # Good
            "501-1000": 0.5,   # Large
            "1000+": 0.3       # Enterprise
        }
        
        for size, score in size_scores.items():
            if size in company_size:
                return score
        
        return 0.5  # Default
    
    def _score_location(self, lead: Lead) -> float:
        """
        Score based on location relevance
        """
        location = (lead.location or "").lower()
        
        # High-value locations (tech hubs)
        high_value_locations = [
            "san francisco", "new york", "boston", "seattle", "austin",
            "london", "berlin", "bangalore", "singapore", "sydney",
            "toronto", "tel aviv", "amsterdam", "paris"
        ]
        
        for hub in high_value_locations:
            if hub in location:
                return 1.0
        
        # US locations (good)
        if "united states" in location or "usa" in location:
            return 0.8
        
        # Remote (neutral)
        if "remote" in location:
            return 0.6
        
        return 0.5  # Default
    
    def get_score_breakdown(self, lead: Lead) -> Dict[str, Any]:
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
                "raw_score": score,
                "weight": weight,
                "weighted_score": weighted
            }
            total += weighted
        
        return {
            "total_score": int(round(total)),
            "components": weighted_scores,
            "weights_used": self.weights
        }