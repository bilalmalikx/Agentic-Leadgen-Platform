"""
Lead Scraper Agent
Multi-source scraping agent with fallback mechanisms
"""

from typing import List, Dict, Any, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class LeadScraperAgent:
    """
    Agent responsible for scraping leads from multiple sources
    Supports: LinkedIn, Twitter, Crunchbase, Company Websites
    """
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=settings.scraping_concurrent_browsers)
        self.sources = {
            "linkedin": self._scrape_linkedin,
            "twitter": self._scrape_twitter,
            "crunchbase": self._scrape_crunchbase,
            "company_website": self._scrape_company_website
        }
    
    async def scrape(
        self,
        query: str,
        sources: List[str],
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Scrape leads from specified sources
        """
        logger.info(f"Scraping {limit} leads for query: {query} from sources: {sources}")
        
        all_leads = []
        
        # Scrape from each source in parallel
        tasks = []
        for source in sources:
            if source in self.sources:
                task = self._scrape_with_retry(
                    source=source,
                    query=query,
                    limit=limit // len(sources)  # Distribute limit
                )
                tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Scraping failed: {result}")
            else:
                all_leads.extend(result)
        
        # Deduplicate within scraped results
        unique_leads = self._deduplicate_by_email(all_leads)
        
        logger.info(f"Scraped {len(unique_leads)} unique leads")
        return unique_leads[:limit]
    
    async def _scrape_with_retry(
        self,
        source: str,
        query: str,
        limit: int,
        max_retries: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Scrape with retry logic
        """
        for attempt in range(max_retries):
            try:
                scrape_func = self.sources[source]
                result = await scrape_func(query, limit)
                return result
            except Exception as e:
                logger.warning(f"Scraping {source} failed (attempt {attempt + 1}): {e}")
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        return []
    
    async def _scrape_linkedin(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Scrape leads from LinkedIn
        """
        logger.info(f"Scraping LinkedIn for: {query}")
        
        # In production, this would use Playwright with proxy rotation
        # For now, return mock data structure
        leads = []
        
        # Simulate scraping delay
        await asyncio.sleep(0.5)
        
        # Mock data (in production, actual scraping happens here)
        for i in range(min(limit, 50)):
            leads.append({
                "source": "linkedin",
                "email": f"linkedin_user_{i}@example.com",
                "first_name": f"LinkedIn{i}",
                "last_name": "User",
                "company_name": f"Company {i}",
                "job_title": "CTO" if i % 3 == 0 else "CEO" if i % 3 == 1 else "Founder",
                "location": "San Francisco, CA",
                "linkedin_url": f"https://linkedin.com/in/user{i}",
                "raw_data": {
                    "profile_summary": f"Experienced professional in {query}",
                    "connections": i * 100
                }
            })
        
        return leads
    
    async def _scrape_twitter(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Scrape leads from Twitter/X
        """
        logger.info(f"Scraping Twitter for: {query}")
        
        await asyncio.sleep(0.5)
        
        leads = []
        for i in range(min(limit, 30)):
            leads.append({
                "source": "twitter",
                "email": f"twitter_user_{i}@example.com",
                "first_name": f"Twitter{i}",
                "last_name": "User",
                "company_name": f"Startup {i}",
                "job_title": "Founder" if i % 2 == 0 else "Investor",
                "location": "Remote",
                "twitter_handle": f"@user{i}",
                "raw_data": {
                    "bio": f"Building something amazing in {query}",
                    "followers": i * 1000,
                    "tweet_count": i * 500
                }
            })
        
        return leads
    
    async def _scrape_crunchbase(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Scrape leads from Crunchbase
        """
        logger.info(f"Scraping Crunchbase for: {query}")
        
        await asyncio.sleep(0.5)
        
        leads = []
        for i in range(min(limit, 20)):
            leads.append({
                "source": "crunchbase",
                "email": f"crunchbase_{i}@example.com",
                "first_name": f"CB{i}",
                "last_name": "Founder",
                "company_name": f"Tech Company {i}",
                "job_title": "Founder & CEO",
                "location": "New York, NY",
                "raw_data": {
                    "company_funding": f"${i * 10}M",
                    "company_size": f"{i * 10 + 5} employees",
                    "founded_year": 2015 + (i % 8)
                }
            })
        
        return leads
    
    async def _scrape_company_website(self, query: str, limit: int) -> List[Dict[str, Any]]:
        """
        Extract leads from company websites
        """
        logger.info(f"Scraping company websites for: {query}")
        
        await asyncio.sleep(0.5)
        
        leads = []
        for i in range(min(limit, 10)):
            leads.append({
                "source": "company_website",
                "email": f"contact{i}@company{i}.com",
                "first_name": f"Contact{i}",
                "last_name": "Person",
                "company_name": f"Website Company {i}",
                "job_title": "Sales Director",
                "location": "Various",
                "company_website": f"https://company{i}.com",
                "raw_data": {
                    "about_text": f"Leading company in {query} space",
                    "contact_page": f"https://company{i}.com/contact"
                }
            })
        
        return leads
    
    def _deduplicate_by_email(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicates by email
        """
        seen_emails = set()
        unique_leads = []
        
        for lead in leads:
            email = lead.get("email", "").lower()
            if email and email not in seen_emails:
                seen_emails.add(email)
                unique_leads.append(lead)
        
        return unique_leads