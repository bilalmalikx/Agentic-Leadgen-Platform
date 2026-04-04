"""
LinkedIn Scraper
Scrapes LinkedIn profiles using Playwright with anti-detection
"""

from typing import List, Dict, Any, Optional
import asyncio
import re

from app.core.logging import get_logger
from app.core.config import settings
from app.scrapers.base import BaseScraper

logger = get_logger(__name__)


class LinkedInScraper(BaseScraper):
    """
    Scraper for LinkedIn profiles
    Requires authentication or cookie-based access
    """
    
    def __init__(self):
        super().__init__(name="linkedin", use_proxy=settings.scraping_proxy_enabled)
        self.base_url = "https://www.linkedin.com"
        self.search_url = f"{self.base_url}/search/results/people/"
    
    async def scrape(
        self,
        query: str,
        limit: int = 50,
        location: Optional[str] = None,
        title: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape LinkedIn profiles based on search query
        """
        logger.info(f"Scraping LinkedIn for query: {query}, limit: {limit}")
        
        results = []
        
        async with self as scraper:
            # Navigate to search page
            page = await self._new_page()
            
            # Build search URL
            search_params = f"?keywords={query.replace(' ', '%20')}"
            if location:
                search_params += f"&location={location.replace(' ', '%20')}"
            if title:
                search_params += f"&title={title.replace(' ', '%20')}"
            
            await page.goto(f"{self.search_url}{search_params}", timeout=30000)
            await self.random_delay(2, 4)
            
            # Scroll to load more results
            scroll_count = 0
            max_scrolls = min(limit // 10, 20)
            
            while scroll_count < max_scrolls and len(results) < limit:
                # Extract profiles from current page
                profiles = await self._extract_profiles(page)
                
                for profile in profiles:
                    if len(results) >= limit:
                        break
                    if profile.get("email") not in [r.get("email") for r in results]:
                        results.append(profile)
                
                # Scroll down
                await page.evaluate("window.scrollBy(0, 800)")
                await self.random_delay(1, 2)
                scroll_count += 1
            
            logger.info(f"LinkedIn scraping completed: {len(results)} profiles found")
            return results[:limit]
    
    async def _extract_profiles(self, page) -> List[Dict[str, Any]]:
        """Extract profile information from search results page"""
        profiles = []
        
        # Wait for results to load
        await page.wait_for_selector(".reusable-search__result-container", timeout=10000)
        
        # Get all result items
        result_items = await page.query_selector_all(".reusable-search__result-container")
        
        for item in result_items[:20]:  # Process up to 20 per scroll
            try:
                # Extract name
                name_elem = await item.query_selector(".entity-result__title-text a")
                name = await name_elem.text_content() if name_elem else None
                
                # Extract headline (title + company)
                headline_elem = await item.query_selector(".entity-result__primary-subtitle")
                headline = await headline_elem.text_content() if headline_elem else None
                
                # Extract location
                location_elem = await item.query_selector(".entity-result__secondary-subtitle")
                location = await location_elem.text_content() if location_elem else None
                
                # Extract profile URL
                profile_url = None
                if name_elem:
                    profile_url = await name_elem.get_attribute("href")
                    if profile_url and not profile_url.startswith("http"):
                        profile_url = f"{self.base_url}{profile_url}"
                
                # Parse headline for job title and company
                job_title = None
                company_name = None
                if headline:
                    parts = headline.split(" at ")
                    if len(parts) == 2:
                        job_title = parts[0].strip()
                        company_name = parts[1].strip()
                    else:
                        job_title = headline.strip()
                
                # Try to get email (LinkedIn doesn't show emails directly)
                # This would require additional scraping of profile page
                email = await self._extract_email_from_profile(profile_url) if profile_url else None
                
                profile_data = {
                    "source": "linkedin",
                    "full_name": name.strip() if name else None,
                    "first_name": name.split()[0] if name else None,
                    "last_name": name.split()[-1] if name and len(name.split()) > 1 else None,
                    "job_title": job_title,
                    "company_name": company_name,
                    "location": location.strip() if location else None,
                    "linkedin_url": profile_url,
                    "email": email,
                    "raw_data": {
                        "headline": headline,
                        "scraped_at": asyncio.get_event_loop().time()
                    }
                }
                
                profiles.append(profile_data)
                
            except Exception as e:
                logger.warning(f"Error extracting LinkedIn profile: {e}")
                continue
        
        return profiles
    
    async def _extract_email_from_profile(self, profile_url: str) -> Optional[str]:
        """
        Extract email from LinkedIn profile (if publicly available)
        Note: Most LinkedIn profiles don't show emails publicly
        """
        # In production, you might:
        # 1. Use email finding APIs
        # 2. Scrape "Contact Info" section (requires login)
        # 3. Use pattern matching on name + company domain
        
        # For now, return None - emails need separate enrichment
        return None
    
    async def scrape_profile(self, profile_url: str) -> Dict[str, Any]:
        """
        Scrape a single LinkedIn profile in detail
        """
        logger.info(f"Scraping LinkedIn profile: {profile_url}")
        
        async with self as scraper:
            page = await self._new_page()
            await page.goto(profile_url, timeout=30000)
            await self.random_delay(2, 3)
            
            profile_data = {
                "source": "linkedin",
                "linkedin_url": profile_url
            }
            
            # Extract name
            name_elem = await page.query_selector(".text-heading-xlarge")
            if name_elem:
                full_name = await name_elem.text_content()
                profile_data["full_name"] = full_name.strip() if full_name else None
                if profile_data["full_name"]:
                    name_parts = profile_data["full_name"].split()
                    profile_data["first_name"] = name_parts[0]
                    profile_data["last_name"] = name_parts[-1] if len(name_parts) > 1 else None
            
            # Extract headline
            headline_elem = await page.query_selector(".text-body-medium")
            if headline_elem:
                headline = await headline_elem.text_content()
                if headline:
                    parts = headline.split(" at ")
                    if len(parts) == 2:
                        profile_data["job_title"] = parts[0].strip()
                        profile_data["company_name"] = parts[1].strip()
                    else:
                        profile_data["job_title"] = headline.strip()
            
            # Extract location
            location_elem = await page.query_selector(".text-body-small")
            if location_elem:
                profile_data["location"] = (await location_elem.text_content()).strip()
            
            # Extract about section
            about_elem = await page.query_selector(".display-flex.ph5 .pv-shared-text-with-see-more")
            if about_elem:
                about_text = await about_elem.text_content()
                profile_data["raw_data"] = {"about": about_text.strip() if about_text else None}
            
            return profile_data