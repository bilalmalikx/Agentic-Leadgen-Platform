"""
Crunchbase Scraper
Scrapes company information from Crunchbase
"""

from typing import List, Dict, Any, Optional
import asyncio
import re

from app.core.logging import get_logger
from app.core.config import settings
from app.scrapers.base import BaseScraper

logger = get_logger(__name__)


class CrunchbaseScraper(BaseScraper):
    """
    Scraper for Crunchbase company data
    """
    
    def __init__(self):
        super().__init__(name="crunchbase", use_proxy=settings.scraping_proxy_enabled)
        self.base_url = "https://www.crunchbase.com"
        self.search_url = f"{self.base_url}/textsearch"
    
    async def scrape(
        self,
        query: str,
        limit: int = 50,
        industry: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape companies from Crunchbase
        """
        logger.info(f"Scraping Crunchbase for query: {query}, limit: {limit}")
        
        results = []
        
        async with self as scraper:
            page = await self._new_page()
            
            # Navigate to search
            search_url = f"{self.search_url}?q={query.replace(' ', '%20')}"
            await page.goto(search_url, timeout=30000)
            await self.random_delay(2, 4)
            
            scroll_count = 0
            max_scrolls = min(limit // 10, 20)
            
            while scroll_count < max_scrolls and len(results) < limit:
                # Extract companies
                companies = await self._extract_companies(page)
                
                for company in companies:
                    if len(results) >= limit:
                        break
                    if company.get("company_name") not in [r.get("company_name") for r in results]:
                        results.append(company)
                
                # Scroll down
                await page.evaluate("window.scrollBy(0, 800)")
                await self.random_delay(1, 2)
                scroll_count += 1
            
            logger.info(f"Crunchbase scraping completed: {len(results)} companies found")
            return results[:limit]
    
    async def _extract_companies(self, page) -> List[Dict[str, Any]]:
        """Extract company information from search results"""
        companies = []
        
        try:
            # Find company result containers
            result_items = await page.query_selector_all('.mat-mdc-card')
            
            for item in result_items[:30]:
                try:
                    company_data = {
                        "source": "crunchbase",
                        "raw_data": {}
                    }
                    
                    # Extract company name
                    name_elem = await item.query_selector('a[data-test="entity-name-link"]')
                    if name_elem:
                        company_data["company_name"] = (await name_elem.text_content()).strip()
                        company_data["crunchbase_url"] = await name_elem.get_attribute("href")
                    
                    # Extract location
                    location_elem = await item.query_selector('[data-test="location"]')
                    if location_elem:
                        company_data["location"] = (await location_elem.text_content()).strip()
                    
                    # Extract description
                    desc_elem = await item.query_selector('[data-test="short_description"]')
                    if desc_elem:
                        company_data["description"] = (await desc_elem.text_content()).strip()
                    
                    # Extract funding info
                    funding_elem = await item.query_selector('[data-test="funding"]')
                    if funding_elem:
                        funding_text = await funding_elem.text_content()
                        company_data["funding_info"] = funding_text.strip() if funding_text else None
                    
                    if company_data.get("company_name"):
                        companies.append(company_data)
                        
                except Exception as e:
                    logger.warning(f"Error extracting Crunchbase company: {e}")
                    continue
                    
        except Exception as e:
            logger.warning(f"Error extracting Crunchbase results: {e}")
        
        return companies
    
    async def scrape_company(self, company_url: str) -> Dict[str, Any]:
        """
        Scrape detailed company information
        """
        logger.info(f"Scraping Crunchbase company: {company_url}")
        
        company_data = {
            "source": "crunchbase",
            "crunchbase_url": company_url
        }
        
        async with self as scraper:
            page = await self._new_page()
            await page.goto(company_url, timeout=30000)
            await self.random_delay(2, 3)
            
            # Extract company name
            name_elem = await page.query_selector('h1')
            if name_elem:
                company_data["company_name"] = (await name_elem.text_content()).strip()
            
            # Extract description
            desc_elem = await page.query_selector('[data-test="description"]')
            if desc_elem:
                company_data["description"] = (await desc_elem.text_content()).strip()
            
            # Extract industry
            industry_elem = await page.query_selector('[data-test="industry"]')
            if industry_elem:
                company_data["industry"] = (await industry_elem.text_content()).strip()
            
            # Extract founded year
            founded_elem = await page.query_selector('[data-test="founded"]')
            if founded_elem:
                founded_text = await founded_elem.text_content()
                company_data["founded_year"] = self._extract_year(founded_text)
            
            # Extract employee count
            employees_elem = await page.query_selector('[data-test="employees"]')
            if employees_elem:
                employees_text = await employees_elem.text_content()
                company_data["employee_count"] = employees_text.strip() if employees_text else None
            
            # Extract funding total
            funding_elem = await page.query_selector('[data-test="funding_total"]')
            if funding_elem:
                funding_text = await funding_elem.text_content()
                company_data["funding_total"] = funding_text.strip() if funding_text else None
            
            # Extract investors
            investor_elements = await page.query_selector_all('[data-test="investors"] a')
            investors = []
            for elem in investor_elements[:10]:
                investor_name = await elem.text_content()
                if investor_name:
                    investors.append(investor_name.strip())
            company_data["investors"] = investors
            
            company_data["raw_data"] = {
                "scraped_at": asyncio.get_event_loop().time()
            }
        
        return company_data
    
    def _extract_year(self, text: Optional[str]) -> Optional[int]:
        """Extract year from text"""
        if not text:
            return None
        
        match = re.search(r'\b(19|20)\d{2}\b', text)
        if match:
            return int(match.group())
        
        return None