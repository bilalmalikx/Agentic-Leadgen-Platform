"""
Proxy Manager
Manages rotating proxies for web scraping to avoid IP blocks
"""

from typing import List, Optional, Dict, Any
import random
import asyncio
from datetime import datetime, timedelta

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class ProxyManager:
    """
    Manages proxy rotation for web scraping
    Supports multiple proxy providers and automatic failover
    """
    
    def __init__(self):
        self.proxies = []
        self.current_proxy_index = 0
        self.failed_proxies = {}
        self._initialized = False
    
    async def initialize(self):
        """Initialize proxy list from configuration"""
        if self._initialized:
            return
        
        # Load proxies from environment or external service
        proxy_urls = settings.scraping_proxy_url
        
        if proxy_urls:
            if isinstance(proxy_urls, str):
                self.proxies = [p.strip() for p in proxy_urls.split(",") if p.strip()]
            else:
                self.proxies = proxy_urls
        
        # If no proxies configured, use default (no proxy)
        if not self.proxies:
            self.proxies = [None]
        
        self._initialized = True
        logger.info(f"Proxy manager initialized with {len(self.proxies)} proxies")
    
    async def get_proxy(self) -> Optional[str]:
        """
        Get next available proxy
        """
        await self.initialize()
        
        if not self.proxies:
            return None
        
        # Try to get a working proxy
        for _ in range(len(self.proxies)):
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            
            # Skip failed proxies
            if proxy in self.failed_proxies:
                failed_time = self.failed_proxies[proxy]
                if datetime.utcnow() - failed_time < timedelta(minutes=5):
                    continue
                else:
                    # Remove from failed after cooldown
                    del self.failed_proxies[proxy]
            
            return proxy
        
        # If all proxies failed, return None (use direct connection)
        logger.warning("All proxies failed, using direct connection")
        return None
    
    async def rotate_proxy(self):
        """Force rotate to next proxy"""
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
        logger.info(f"Rotated to proxy index {self.current_proxy_index}")
    
    async def mark_failed(self, proxy: str):
        """Mark a proxy as failed"""
        self.failed_proxies[proxy] = datetime.utcnow()
        logger.warning(f"Proxy marked as failed: {proxy}")
        
        # Rotate to next proxy
        await self.rotate_proxy()
    
    async def add_proxy(self, proxy: str):
        """Add a new proxy to the pool"""
        if proxy not in self.proxies:
            self.proxies.append(proxy)
            logger.info(f"Added new proxy: {proxy}")
    
    async def remove_proxy(self, proxy: str):
        """Remove a proxy from the pool"""
        if proxy in self.proxies:
            self.proxies.remove(proxy)
            logger.info(f"Removed proxy: {proxy}")
    
    def get_proxy_count(self) -> int:
        """Get number of available proxies"""
        return len([p for p in self.proxies if p not in self.failed_proxies])
    
    def get_stats(self) -> Dict[str, Any]:
        """Get proxy manager statistics"""
        return {
            "total_proxies": len(self.proxies),
            "active_proxies": self.get_proxy_count(),
            "failed_proxies": len(self.failed_proxies),
            "current_index": self.current_proxy_index
        }


# Singleton instance
_proxy_manager = None


def get_proxy_manager() -> ProxyManager:
    """Get or create proxy manager instance"""
    global _proxy_manager
    if _proxy_manager is None:
        _proxy_manager = ProxyManager()
    return _proxy_manager