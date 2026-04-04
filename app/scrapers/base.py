"""
Base Scraper Class
All scrapers inherit from this base class with common functionality
"""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
import asyncio
import time
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page, Playwright

from app.core.logging import get_logger
from app.core.config import settings
from app.scrapers.proxy_manager import get_proxy_manager
from app.scrapers.user_agent_pool import get_user_agent

logger = get_logger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for all web scrapers
    Provides common functionality: browser management, retries, proxy rotation
    """
    
    def __init__(self, name: str, use_proxy: bool = False):
        self.name = name
        self.use_proxy = use_proxy
        self.proxy_manager = get_proxy_manager() if use_proxy else None
        self.browser: Optional[Browser] = None
        self.playwright: Optional[Playwright] = None
        self._retry_count = 0
        self._metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_duration_ms": 0
        }
    
    async def __aenter__(self):
        """Setup browser context"""
        await self._setup_browser()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup browser context"""
        await self._cleanup_browser()
    
    async def _setup_browser(self):
        """Initialize browser with optional proxy"""
        self.playwright = await async_playwright().start()
        
        browser_options = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        }
        
        # Add proxy if enabled
        if self.use_proxy and self.proxy_manager:
            proxy = await self.proxy_manager.get_proxy()
            if proxy:
                browser_options["proxy"] = {"server": proxy}
        
        self.browser = await self.playwright.chromium.launch(**browser_options)
        logger.info(f"Browser launched for scraper: {self.name}")
    
    async def _cleanup_browser(self):
        """Close browser and cleanup"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info(f"Browser closed for scraper: {self.name}")
    
    async def _new_page(self) -> Page:
        """Create new page with random user agent"""
        context = await self.browser.new_context(
            user_agent=get_user_agent(),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York"
        )
        return await context.new_page()
    
    @abstractmethod
    async def scrape(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """
        Main scraping method - must be implemented by child classes
        """
        pass
    
    async def scrape_with_retry(
        self,
        max_retries: int = 3,
        delay: float = 2.0,
        *args, **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Scrape with retry logic and exponential backoff
        """
        start_time = time.time()
        self._metrics["total_requests"] += 1
        
        for attempt in range(max_retries):
            try:
                result = await self.scrape(*args, **kwargs)
                
                duration_ms = (time.time() - start_time) * 1000
                self._metrics["successful_requests"] += 1
                self._metrics["total_duration_ms"] += duration_ms
                
                logger.info(
                    f"Scraper {self.name} succeeded after {attempt + 1} attempts "
                    f"in {duration_ms:.2f}ms"
                )
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    f"Scraper {self.name} attempt {attempt + 1}/{max_retries} failed: {e}"
                )
                
                if attempt == max_retries - 1:
                    self._metrics["failed_requests"] += 1
                    self._metrics["total_duration_ms"] += duration_ms
                    raise
                
                # Exponential backoff
                wait_time = delay * (2 ** attempt)
                await asyncio.sleep(wait_time)
                
                # Rotate proxy if available
                if self.use_proxy and self.proxy_manager:
                    await self.proxy_manager.rotate_proxy()
                    await self._cleanup_browser()
                    await self._setup_browser()
        
        return []
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get scraper performance metrics"""
        total = self._metrics["total_requests"]
        success_rate = (
            (self._metrics["successful_requests"] / total * 100)
            if total > 0 else 0
        )
        
        return {
            "scraper_name": self.name,
            "total_requests": self._metrics["total_requests"],
            "successful_requests": self._metrics["successful_requests"],
            "failed_requests": self._metrics["failed_requests"],
            "success_rate": round(success_rate, 2),
            "average_duration_ms": round(
                self._metrics["total_duration_ms"] / total if total > 0 else 0, 2
            )
        }
    
    async def random_delay(self, min_seconds: float = 1.0, max_seconds: float = 3.0):
        """Add random delay to avoid rate limiting"""
        import random
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
    
    async def safe_click(self, page: Page, selector: str, timeout: int = 5000):
        """Safely click element with retry"""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            await page.click(selector)
            return True
        except Exception as e:
            logger.warning(f"Failed to click {selector}: {e}")
            return False
    
    async def safe_fill(self, page: Page, selector: str, value: str, timeout: int = 5000):
        """Safely fill input with retry"""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            await page.fill(selector, value)
            return True
        except Exception as e:
            logger.warning(f"Failed to fill {selector}: {e}")
            return False
    
    async def extract_text(self, page: Page, selector: str) -> Optional[str]:
        """Extract text from element safely"""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.text_content()
            return None
        except Exception:
            return None
    
    async def extract_attribute(
        self,
        page: Page,
        selector: str,
        attribute: str
    ) -> Optional[str]:
        """Extract attribute value from element safely"""
        try:
            element = await page.query_selector(selector)
            if element:
                return await element.get_attribute(attribute)
            return None
        except Exception:
            return None
    
    def scrape_sync(self, *args, **kwargs) -> List[Dict[str, Any]]:
        """
        Synchronous wrapper for scraping (for Celery tasks)
        """
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(self.scrape_with_retry(*args, **kwargs))
        finally:
            loop.close()