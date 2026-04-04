"""
Twitter/X Scraper
Scrapes Twitter/X profiles using API or Playwright
"""

from typing import List, Dict, Any, Optional
import asyncio
import re

from app.core.logging import get_logger
from app.core.config import settings
from app.scrapers.base import BaseScraper

logger = get_logger(__name__)


class TwitterScraper(BaseScraper):
    """
    Scraper for Twitter/X profiles
    Uses either API (if token available) or Playwright
    """
    
    def __init__(self):
        super().__init__(name="twitter", use_proxy=settings.scraping_proxy_enabled)
        self.base_url = "https://twitter.com"
        self.api_token = settings.twitter_bearer_token
    
    async def scrape(
        self,
        query: str,
        limit: int = 50,
        type: str = "users"
    ) -> List[Dict[str, Any]]:
        """
        Scrape Twitter profiles based on search query
        """
        logger.info(f"Scraping Twitter for query: {query}, limit: {limit}")
        
        results = []
        
        # Try API first if token available
        if self.api_token:
            results = await self._scrape_via_api(query, limit, type)
        
        # Fallback to Playwright scraping
        if not results:
            results = await self._scrape_via_playwright(query, limit, type)
        
        logger.info(f"Twitter scraping completed: {len(results)} profiles found")
        return results[:limit]
    
    async def _scrape_via_api(
        self,
        query: str,
        limit: int,
        type: str
    ) -> List[Dict[str, Any]]:
        """Scrape using Twitter API"""
        import httpx
        
        results = []
        
        try:
            async with httpx.AsyncClient() as client:
                headers = {
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json"
                }
                
                if type == "users":
                    url = f"https://api.twitter.com/2/users/by?usernames={query}"
                else:
                    url = f"https://api.twitter.com/2/tweets/search/recent?query={query}&max_results={min(limit, 100)}"
                
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if type == "users" and "data" in data:
                        for user in data["data"]:
                            results.append({
                                "source": "twitter",
                                "twitter_handle": user.get("username"),
                                "full_name": user.get("name"),
                                "raw_data": user
                            })
                    elif "data" in data:
                        for tweet in data["data"]:
                            results.append({
                                "source": "twitter",
                                "tweet_id": tweet.get("id"),
                                "tweet_text": tweet.get("text"),
                                "raw_data": tweet
                            })
                
        except Exception as e:
            logger.warning(f"Twitter API scraping failed: {e}")
        
        return results
    
    async def _scrape_via_playwright(
        self,
        query: str,
        limit: int,
        type: str
    ) -> List[Dict[str, Any]]:
        """Scrape using Playwright (fallback)"""
        results = []
        
        async with self as scraper:
            page = await self._new_page()
            
            # Navigate to Twitter search
            search_url = f"{self.base_url}/search?q={query.replace(' ', '%20')}&src=typed_query"
            await page.goto(search_url, timeout=30000)
            await self.random_delay(3, 5)
            
            # Handle login if needed (Twitter requires login for search)
            # In production, you would need to handle authentication
            
            scroll_count = 0
            max_scrolls = min(limit // 10, 15)
            
            while scroll_count < max_scrolls and len(results) < limit:
                # Extract user handles from tweets
                handles = await self._extract_handles(page)
                
                for handle in handles:
                    if handle not in [r.get("twitter_handle") for r in results]:
                        results.append({
                            "source": "twitter",
                            "twitter_handle": handle,
                            "scraped_at": asyncio.get_event_loop().time()
                        })
                
                # Scroll down
                await page.evaluate("window.scrollBy(0, 800)")
                await self.random_delay(1, 2)
                scroll_count += 1
            
            return results
    
    async def _extract_handles(self, page) -> List[str]:
        """Extract Twitter handles from search results"""
        handles = []
        
        try:
            # Find tweet elements
            tweet_elements = await page.query_selector_all('[data-testid="tweet"]')
            
            for tweet in tweet_elements[:30]:
                try:
                    # Find author link
                    author_link = await tweet.query_selector('a[href^="/"]')
                    if author_link:
                        href = await author_link.get_attribute("href")
                        if href and href.startswith("/") and len(href) > 1:
                            handle = href[1:].split("/")[0]
                            if handle and handle not in handles:
                                handles.append(handle)
                except Exception:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error extracting handles: {e}")
        
        return handles
    
    async def scrape_profile(self, handle: str) -> Dict[str, Any]:
        """
        Scrape a single Twitter profile
        """
        logger.info(f"Scraping Twitter profile: @{handle}")
        
        profile_data = {
            "source": "twitter",
            "twitter_handle": handle
        }
        
        # Try API first
        if self.api_token:
            api_data = await self._scrape_via_api(handle, 1, "users")
            if api_data:
                profile_data.update(api_data[0])
                return profile_data
        
        # Fallback to Playwright
        async with self as scraper:
            page = await self._new_page()
            await page.goto(f"{self.base_url}/{handle}", timeout=30000)
            await self.random_delay(2, 3)
            
            # Extract name
            name_elem = await page.query_selector('div[data-testid="UserName"]')
            if name_elem:
                name_text = await name_elem.text_content()
                if name_text:
                    profile_data["full_name"] = name_text.strip()
            
            # Extract bio
            bio_elem = await page.query_selector('div[data-testid="UserDescription"]')
            if bio_elem:
                bio = await bio_elem.text_content()
                profile_data["bio"] = bio.strip() if bio else None
            
            # Extract location
            location_elem = await page.query_selector('span[data-testid="UserLocation"]')
            if location_elem:
                location = await location_elem.text_content()
                profile_data["location"] = location.strip() if location else None
            
            # Extract follower count
            stats = await page.query_selector_all('a[href$="/followers"] span')
            if stats and len(stats) > 0:
                followers_text = await stats[0].text_content()
                if followers_text:
                    profile_data["followers"] = self._parse_count(followers_text)
            
            profile_data["raw_data"] = {
                "scraped_at": asyncio.get_event_loop().time()
            }
        
        return profile_data
    
    def _parse_count(self, text: str) -> int:
        """Parse follower count from text (e.g., '1.2M' -> 1200000)"""
        text = text.strip().lower()
        
        multipliers = {
            'k': 1000,
            'm': 1000000,
            'b': 1000000000
        }
        
        for suffix, multiplier in multipliers.items():
            if suffix in text:
                number = float(text.replace(suffix, ''))
                return int(number * multiplier)
        
        try:
            return int(text.replace(',', ''))
        except ValueError:
            return 0