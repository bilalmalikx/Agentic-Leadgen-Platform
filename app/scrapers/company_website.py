"""
Company Website Scraper
Extracts contact information and company details from websites
"""

from typing import List, Dict, Any, Optional
import asyncio
import re
from urllib.parse import urljoin, urlparse

from app.core.logging import get_logger
from app.core.config import settings
from app.scrapers.base import BaseScraper

logger = get_logger(__name__)


class CompanyWebsiteScraper(BaseScraper):
    """
    Scraper for extracting leads from company websites
    Finds contact emails, phone numbers, and key people
    """
    
    def __init__(self):
        super().__init__(name="company_website", use_proxy=settings.scraping_proxy_enabled)
        
        # Email pattern
        self.email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        )
        
        # Phone pattern
        self.phone_pattern = re.compile(
            r'\b[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{4,10}\b'
        )
    
    async def scrape(
        self,
        url: str,
        depth: int = 1,
        find_emails: bool = True,
        find_people: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Scrape company website for contact information
        """
        logger.info(f"Scraping company website: {url}")
        
        results = []
        visited_urls = set()
        
        async with self as scraper:
            urls_to_visit = [(url, 0)]
            
            while urls_to_visit and len(results) < 50:
                current_url, current_depth = urls_to_visit.pop(0)
                
                if current_url in visited_urls or current_depth > depth:
                    continue
                
                visited_urls.add(current_url)
                
                page = await self._new_page()
                
                try:
                    await page.goto(current_url, timeout=30000)
                    await self.random_delay(1, 2)
                    
                    # Get page content
                    content = await page.content()
                    
                    # Extract emails
                    if find_emails:
                        emails = self._extract_emails(content, current_url)
                        for email in emails:
                            if email not in [r.get("email") for r in results]:
                                results.append({
                                    "source": "company_website",
                                    "email": email,
                                    "found_on": current_url,
                                    "type": "email"
                                })
                    
                    # Extract phone numbers
                    phones = self._extract_phones(content)
                    for phone in phones[:5]:
                        results.append({
                            "source": "company_website",
                            "phone": phone,
                            "found_on": current_url,
                            "type": "phone"
                        })
                    
                    # Extract people (from team/about pages)
                    if find_people and ("team" in current_url.lower() or "about" in current_url.lower()):
                        people = await self._extract_people(page)
                        for person in people[:10]:
                            results.append({
                                "source": "company_website",
                                "full_name": person.get("name"),
                                "job_title": person.get("title"),
                                "found_on": current_url,
                                "type": "person"
                            })
                    
                    # Find links to explore further
                    if current_depth < depth:
                        links = await page.query_selector_all('a[href]')
                        for link in links[:20]:
                            href = await link.get_attribute("href")
                            if href:
                                full_url = urljoin(current_url, href)
                                parsed = urlparse(full_url)
                                
                                # Only stay on same domain
                                if parsed.netloc == urlparse(url).netloc:
                                    if full_url not in visited_urls:
                                        urls_to_visit.append((full_url, current_depth + 1))
                    
                except Exception as e:
                    logger.warning(f"Error scraping {current_url}: {e}")
                
                finally:
                    await page.close()
        
        logger.info(f"Company website scraping completed: {len(results)} items found")
        return results
    
    def _extract_emails(self, content: str, page_url: str) -> List[str]:
        """Extract email addresses from page content"""
        emails = set()
        
        for match in self.email_pattern.finditer(content):
            email = match.group().lower()
            
            # Filter out common false positives
            if not self._is_valid_email(email):
                continue
            
            # Prefer business emails over generic
            if any(domain in email for domain in ["gmail", "yahoo", "hotmail", "outlook"]):
                continue
            
            emails.add(email)
        
        return list(emails)
    
    def _extract_phones(self, content: str) -> List[str]:
        """Extract phone numbers from page content"""
        phones = set()
        
        for match in self.phone_pattern.finditer(content):
            phone = match.group()
            if len(phone) >= 10:
                phones.add(phone)
        
        return list(phones)
    
    async def _extract_people(self, page) -> List[Dict[str, Any]]:
        """Extract people information from team/about page"""
        people = []
        
        try:
            # Look for person cards/containers
            person_elements = await page.query_selector_all('.person, .team-member, .profile, .card')
            
            for elem in person_elements[:20]:
                person = {}
                
                # Extract name
                name_elem = await elem.query_selector('h3, h4, .name, .person-name')
                if name_elem: