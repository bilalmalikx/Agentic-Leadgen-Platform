"""
Browser Pool
Manages a pool of browser instances for parallel scraping
"""

from typing import List, Optional, Dict, Any
import asyncio
from playwright.async_api import async_playwright, Browser, Playwright

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class BrowserPool:
    """
    Pool of browser instances for parallel web scraping
    """
    
    def __init__(self, max_browsers: int = 5):
        self.max_browsers = max_browsers
        self.browsers: List[Browser] = []
        self.playwright: Optional[Playwright] = None
        self.available_browsers: asyncio.Queue = asyncio.Queue()
        self._initialized = False
    
    async def initialize(self):
        """Initialize browser pool"""
        if self._initialized:
            return
        
        self.playwright = await async_playwright().start()
        
        for i in range(self.max_browsers):
            browser = await self._create_browser()
            self.browsers.append(browser)
            await self.available_browsers.put(browser)
        
        self._initialized = True
        logger.info(f"Browser pool initialized with {self.max_browsers} browsers")
    
    async def _create_browser(self) -> Browser:
        """Create a new browser instance"""
        browser = await self.playwright.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox"
            ]
        )
        return browser
    
    async def get_browser(self, timeout: float = 30.0) -> Browser:
        """
        Get an available browser from the pool
        """
        await self.initialize()
        
        try:
            browser = await asyncio.wait_for(
                self.available_browsers.get(),
                timeout=timeout
            )
            return browser
        except asyncio.TimeoutError:
            raise Exception("No browsers available in pool")
    
    async def return_browser(self, browser: Browser):
        """
        Return a browser to the pool
        """
        await self.available_browsers.put(browser)
    
    async def close_all(self):
        """Close all browsers in the pool"""
        for browser in self.browsers:
            try:
                await browser.close()
            except Exception as e:
                logger.warning(f"Error closing browser: {e}")
        
        if self.playwright:
            await self.playwright.stop()
        
        self._initialized = False
        logger.info("Browser pool closed")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics"""
        return {
            "total_browsers": len(self.browsers),
            "available_browsers": self.available_browsers.qsize(),
            "max_browsers": self.max_browsers,
            "initialized": self._initialized
        }


# Singleton instance
_browser_pool = None


def get_browser_pool() -> BrowserPool:
    """Get or create browser pool instance"""
    global _browser_pool
    if _browser_pool is None:
        _browser_pool = BrowserPool(max_browsers=settings.scraping_concurrent_browsers)
    return _browser_pool