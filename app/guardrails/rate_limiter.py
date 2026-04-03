"""
Rate Limiter Guardrail
Implements token bucket and sliding window rate limiting
"""

import time
from typing import Tuple, Optional, Dict
from dataclasses import dataclass
from enum import Enum

from app.core.redis_client import cache_get, cache_set, increment_counter
from app.core.logging import get_logger

logger = get_logger(__name__)


class LimitType(Enum):
    """Type of rate limit"""
    USER = "user"
    IP = "ip"
    API_KEY = "api_key"
    ENDPOINT = "endpoint"


@dataclass
class RateLimitConfig:
    """Configuration for rate limit"""
    limit: int  # Number of requests
    window_seconds: int  # Time window in seconds
    block_seconds: int = 0  # Block duration after exceeding


class SlidingWindowCounter:
    """
    Sliding window counter algorithm
    More accurate than fixed window
    """
    
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
    
    async def check(self, key: str) -> Tuple[bool, int]:
        """
        Check if request is allowed
        Returns (allowed, remaining)
        """
        now = int(time.time())
        window_key = f"ratelimit:sliding:{key}"
        
        # Get current window counts
        current_window = await cache_get(window_key) or {}
        
        # Clean old entries
        cutoff = now - self.window_seconds
        current_window = {
            k: v for k, v in current_window.items()
            if int(k) > cutoff
        }
        
        # Count requests in window
        total_requests = sum(current_window.values())
        
        if total_requests >= self.limit:
            return False, 0
        
        # Add current request
        current_window[str(now)] = current_window.get(str(now), 0) + 1
        await cache_set(window_key, current_window, self.window_seconds + 60)
        
        remaining = self.limit - (total_requests + 1)
        return True, remaining


class RateLimiter:
    """
    Main rate limiter class
    Supports multiple strategies and limits
    """
    
    DEFAULT_CONFIGS = {
        LimitType.USER: RateLimitConfig(limit=100, window_seconds=60),
        LimitType.IP: RateLimitConfig(limit=50, window_seconds=60),
        LimitType.API_KEY: RateLimitConfig(limit=1000, window_seconds=3600),
        LimitType.ENDPOINT: RateLimitConfig(limit=10, window_seconds=1),
    }
    
    def __init__(
        self,
        identifier: str,
        limit_type: LimitType = LimitType.IP,
        custom_config: Optional[RateLimitConfig] = None
    ):
        self.identifier = identifier
        self.limit_type = limit_type
        
        config = custom_config or self.DEFAULT_CONFIGS.get(limit_type)
        if not config:
            config = RateLimitConfig(limit=100, window_seconds=60)
        
        self.limit = config.limit
        self.window_seconds = config.window_seconds
        self.block_seconds = config.block_seconds
        
        # Use sliding window for accuracy
        self.counter = SlidingWindowCounter(self.limit, self.window_seconds)
    
    async def check_limit(self) -> Tuple[bool, int, Optional[int]]:
        """
        Check if request is within limit
        Returns (allowed, remaining, retry_after)
        """
        key = f"{self.limit_type.value}:{self.identifier}"
        
        # Check if blocked
        block_key = f"ratelimit:blocked:{key}"
        blocked_until = await cache_get(block_key)
        
        if blocked_until and blocked_until > time.time():
            retry_after = int(blocked_until - time.time())
            return False, 0, retry_after
        
        # Check rate limit
        allowed, remaining = await self.counter.check(key)
        
        if not allowed and self.block_seconds > 0:
            # Block the user
            block_until = time.time() + self.block_seconds
            await cache_set(block_key, block_until, self.block_seconds)
            retry_after = self.block_seconds
            return False, 0, retry_after
        
        return allowed, remaining, None
    
    async def get_remaining(self) -> int:
        """Get remaining requests in current window"""
        key = f"{self.limit_type.value}:{self.identifier}"
        window_key = f"ratelimit:sliding:{key}"
        
        current_window = await cache_get(window_key) or {}
        cutoff = int(time.time()) - self.window_seconds
        current_window = {
            k: v for k, v in current_window.items()
            if int(k) > cutoff
        }
        
        total_requests = sum(current_window.values())
        return max(0, self.limit - total_requests)
    
    async def reset(self):
        """Reset rate limit for identifier"""
        key = f"{self.limit_type.value}:{self.identifier}"
        window_key = f"ratelimit:sliding:{key}"
        await cache_set(window_key, {}, 1)
        logger.info(f"Rate limit reset for {key}")


class RateLimiterFactory:
    """Factory to create rate limiters for different contexts"""
    
    @staticmethod
    def for_user(user_id: str) -> RateLimiter:
        """Create rate limiter for user"""
        return RateLimiter(
            identifier=user_id,
            limit_type=LimitType.USER
        )
    
    @staticmethod
    def for_ip(ip_address: str) -> RateLimiter:
        """Create rate limiter for IP"""
        return RateLimiter(
            identifier=ip_address,
            limit_type=LimitType.IP
        )
    
    @staticmethod
    def for_api_key(api_key_hash: str) -> RateLimiter:
        """Create rate limiter for API key"""
        return RateLimiter(
            identifier=api_key_hash,
            limit_type=LimitType.API_KEY,
            custom_config=RateLimitConfig(limit=1000, window_seconds=3600)
        )
    
    @staticmethod
    def for_endpoint(endpoint: str) -> RateLimiter:
        """Create rate limiter for specific endpoint"""
        return RateLimiter(
            identifier=endpoint,
            limit_type=LimitType.ENDPOINT,
            custom_config=RateLimitConfig(limit=10, window_seconds=1)
        )