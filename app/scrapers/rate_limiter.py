"""
Rate Limiter for Scraping
Source-specific rate limiting to avoid blocks
"""

from typing import Dict, Any
import time
import asyncio
from collections import deque

from app.core.logging import get_logger

logger = get_logger(__name__)


class ScrapingRateLimiter:
    """
    Rate limiter for web scraping with per-source limits
    """
    
    # Default rate limits (requests per second per source)
    DEFAULT_LIMITS = {
        "linkedin": 10,      # 10 requests per second
        "twitter": 30,       # 30 requests per second
        "crunchbase": 20,    # 20 requests per second
        "company_website": 50,  # 50 requests per second
        "default": 20
    }
    
    def __init__(self):
        self.request_times: Dict[str, deque] = {}
        self.limits = self.DEFAULT_LIMITS.copy()
    
    def set_limit(self, source: str, requests_per_second: int):
        """Set custom rate limit for a source"""
        self.limits[source] = requests_per_second
        logger.info(f"Rate limit for {source} set to {requests_per_second} req/s")
    
    async def wait_if_needed(self, source: str):
        """
        Wait if rate limit would be exceeded
        """
        limit = self.limits.get(source, self.limits["default"])
        
        if source not in self.request_times:
            self.request_times[source] = deque(maxlen=limit)
        
        # Clean old entries (older than 1 second)
        now = time.time()
        while self.request_times[source] and self.request_times[source][0] < now - 1:
            self.request_times[source].popleft()
        
        # Check if we need to wait
        if len(self.request_times[source]) >= limit:
            # Calculate wait time
            oldest = self.request_times[source][0]
            wait_time = 1 - (now - oldest)
            if wait_time > 0:
                logger.debug(f"Rate limit hit for {source}, waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)
        
        # Record this request
        self.request_times[source].append(time.time())
    
    async def execute_with_limit(self, source: str, func, *args, **kwargs):
        """
        Execute a function with rate limiting
        """
        await self.wait_if_needed(source)
        return await func(*args, **kwargs)
    
    def get_stats(self, source: str) -> Dict[str, Any]:
        """Get rate limit statistics for a source"""
        if source not in self.request_times:
            return {"source": source, "requests_last_second": 0, "limit": self.limits.get(source, self.limits["default"])}
        
        now = time.time()
        recent_requests = [t for t in self.request_times[source] if t > now - 1]
        
        return {
            "source": source,
            "requests_last_second": len(recent_requests),
            "limit": self.limits.get(source, self.limits["default"]),
            "remaining": max(0, self.limits.get(source, self.limits["default"]) - len(recent_requests))
        }


# Singleton instance
_rate_limiter = None


def get_scraping_rate_limiter() -> ScrapingRateLimiter:
    """Get or create scraping rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = ScrapingRateLimiter()
    return _rate_limiter