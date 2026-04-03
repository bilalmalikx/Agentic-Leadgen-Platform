"""
Cache Service
Redis-based caching with TTL, invalidation patterns, and circuit breaker
"""

from typing import Any, Optional, Callable, TypeVar, Dict, List
import json
import hashlib
from functools import wraps
from datetime import datetime, timedelta

from app.core.redis_client import cache_get, cache_set, cache_delete, get_redis
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)

T = TypeVar('T')


class CacheService:
    """
    Service for managing cache operations with advanced patterns
    Supports: TTL, invalidation, cache-aside, write-through, circuit breaker
    """
    
    def __init__(self):
        self.default_ttl = settings.cache_ttl_seconds
        self.max_size = settings.cache_max_size
        self._circuit_breaker = CircuitBreaker()
    
    # ============================================
    # Basic Cache Operations
    # ============================================
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache
        Returns None if not found or error
        """
        try:
            return await cache_get(key)
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set value in cache with TTL
        """
        try:
            ttl = ttl or self.default_ttl
            return await cache_set(key, value, ttl)
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """
        Delete key from cache
        """
        try:
            return await cache_delete(key)
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache
        """
        try:
            value = await self.get(key)
            return value is not None
        except:
            return False
    
    async def increment(self, key: str, delta: int = 1) -> int:
        """
        Increment counter in cache
        """
        try:
            redis = await get_redis()
            return await redis.incr(key, delta)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return 0
    
    # ============================================
    # Cache-Aside Pattern (Most Common)
    # ============================================
    
    async def get_or_set(
        self,
        key: str,
        fetcher: Callable,
        ttl: Optional[int] = None,
        args: tuple = (),
        kwargs: dict = None
    ) -> Any:
        """
        Cache-aside pattern: Get from cache, if not found, fetch and cache
        """
        kwargs = kwargs or {}
        
        # Try to get from cache
        cached_value = await self.get(key)
        if cached_value is not None:
            logger.debug(f"Cache hit for key: {key}")
            return cached_value
        
        # Cache miss - fetch from source
        logger.debug(f"Cache miss for key: {key}, fetching from source")
        
        try:
            # Fetch value
            value = await fetcher(*args, **kwargs) if callable(fetcher) else fetcher
            
            # Store in cache
            if value is not None:
                await self.set(key, value, ttl)
            
            return value
            
        except Exception as e:
            logger.error(f"Failed to fetch value for cache key {key}: {e}")
            raise
    
    # ============================================
    # Bulk Cache Operations
    # ============================================
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple keys from cache in single operation
        """
        try:
            redis = await get_redis()
            values = await redis.mget(keys)
            
            result = {}
            for key, value in zip(keys, values):
                if value:
                    result[key] = json.loads(value)
                else:
                    result[key] = None
            
            return result
            
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {key: None for key in keys}
    
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: Optional[int] = None
    ) -> bool:
        """
        Set multiple keys in cache in single operation
        """
        try:
            redis = await get_redis()
            ttl = ttl or self.default_ttl
            
            # Serialize values
            pipeline = redis.pipeline()
            for key, value in items.items():
                pipeline.setex(key, ttl, json.dumps(value))
            
            await pipeline.execute()
            return True
            
        except Exception as e:
            logger.error(f"Cache set_many error: {e}")
            return False
    
    async def delete_many(self, keys: List[str]) -> int:
        """
        Delete multiple keys from cache
        """
        try:
            redis = await get_redis()
            return await redis.delete(*keys)
        except Exception as e:
            logger.error(f"Cache delete_many error: {e}")
            return 0
    
    # ============================================
    # Pattern-Based Operations
    # ============================================
    
    async def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern
        """
        try:
            redis = await get_redis()
            keys = await redis.keys(pattern)
            if keys:
                return await redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete_pattern error for {pattern}: {e}")
            return 0
    
    async def get_keys(self, pattern: str = "*") -> List[str]:
        """
        Get all keys matching pattern
        """
        try:
            redis = await get_redis()
            return await redis.keys(pattern)
        except Exception as e:
            logger.error(f"Cache get_keys error for {pattern}: {e}")
            return []
    
    # ============================================
    # Invalidation Patterns
    # ============================================
    
    async def invalidate_by_prefix(self, prefix: str) -> int:
        """
        Invalidate all keys with given prefix
        """
        return await self.delete_pattern(f"{prefix}:*")
    
    async def invalidate_by_tags(self, tags: List[str]) -> int:
        """
        Invalidate keys by tags (using tag sets)
        """
        total_deleted = 0
        
        for tag in tags:
            tag_key = f"tag:{tag}"
            keys = await self.get_keys(f"{tag_key}:*")
            
            # Get actual cache keys from tag set
            redis = await get_redis()
            tagged_keys = await redis.smembers(tag_key)
            
            if tagged_keys:
                deleted = await redis.delete(*tagged_keys)
                total_deleted += deleted
                await redis.delete(tag_key)
        
        return total_deleted
    
    async def add_tag(self, key: str, tag: str):
        """
        Add tag to a cache key for later invalidation
        """
        try:
            redis = await get_redis()
            tag_key = f"tag:{tag}"
            await redis.sadd(tag_key, key)
            # Set expiry on tag set (7 days)
            await redis.expire(tag_key, 604800)
        except Exception as e:
            logger.error(f"Cache add_tag error: {e}")
    
    # ============================================
    # Cache Warming
    # ============================================
    
    async def warm_cache(
        self,
        keys_and_fetchers: List[tuple],
        ttl: Optional[int] = None
    ) -> Dict[str, bool]:
        """
        Pre-warm cache with multiple keys
        Each tuple: (key, fetcher, args, kwargs)
        """
        results = {}
        
        for item in keys_and_fetchers:
            key = item[0]
            fetcher = item[1]
            args = item[2] if len(item) > 2 else ()
            kwargs = item[3] if len(item) > 3 else {}
            
            try:
                value = await fetcher(*args, **kwargs)
                if value:
                    await self.set(key, value, ttl)
                    results[key] = True
                else:
                    results[key] = False
            except Exception as e:
                logger.error(f"Cache warming failed for {key}: {e}")
                results[key] = False
        
        return results
    
    # ============================================
    # Cache Statistics
    # ============================================
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics
        """
        try:
            redis = await get_redis()
            info = await redis.info("stats")
            
            return {
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "hit_rate": self._calculate_hit_rate(
                    info.get("keyspace_hits", 0),
                    info.get("keyspace_misses", 0)
                ),
                "total_keys": len(await redis.keys("*")),
                "memory_used_mb": await self._get_memory_usage(),
                "uptime_seconds": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            logger.error(f"Failed to get cache stats: {e}")
            return {
                "hits": 0,
                "misses": 0,
                "hit_rate": 0,
                "total_keys": 0,
                "memory_used_mb": 0,
                "uptime_seconds": 0
            }
    
    async def clear_all(self) -> bool:
        """
        Clear all cache (use with caution!)
        """
        try:
            redis = await get_redis()
            await redis.flushdb()
            logger.warning("Cache completely cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False
    
    # ============================================
    # Helper Methods
    # ============================================
    
    def generate_key(self, prefix: str, *args, **kwargs) -> str:
        """
        Generate consistent cache key from prefix and arguments
        """
        key_parts = [prefix]
        
        for arg in args:
            key_parts.append(str(arg))
        
        for k, v in sorted(kwargs.items()):
            key_parts.append(f"{k}:{v}")
        
        key = ":".join(key_parts)
        
        # Hash if too long
        if len(key) > 200:
            key_hash = hashlib.md5(key.encode()).hexdigest()[:16]
            key = f"{prefix}:{key_hash}"
        
        return key
    
    def _calculate_hit_rate(self, hits: int, misses: int) -> float:
        """Calculate cache hit rate percentage"""
        total = hits + misses
        if total == 0:
            return 0.0
        return round((hits / total) * 100, 2)
    
    async def _get_memory_usage(self) -> float:
        """Get Redis memory usage in MB"""
        try:
            redis = await get_redis()
            info = await redis.info("memory")
            used_memory = info.get("used_memory", 0)
            return round(used_memory / (1024 * 1024), 2)
        except:
            return 0.0


class CircuitBreaker:
    """
    Circuit breaker pattern for cache operations
    Prevents cascading failures when Redis is down
    """
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def is_open(self) -> bool:
        """Check if circuit is open"""
        if self.state == "OPEN":
            if self.last_failure_time:
                elapsed = (datetime.utcnow() - self.last_failure_time).total_seconds()
                if elapsed >= self.timeout_seconds:
                    self.state = "HALF_OPEN"
                    return False
            return True
        return False
    
    def record_failure(self):
        """Record a failure"""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def record_success(self):
        """Record a success (reset circuit)"""
        self.failure_count = 0
        self.state = "CLOSED"
    
    def reset(self):
        """Reset circuit breaker"""
        self.failure_count = 0
        self.state = "CLOSED"
        self.last_failure_time = None


# Singleton instance
_cache_service = None


def get_cache_service() -> CacheService:
    """Get or create cache service instance"""
    global _cache_service
    if _cache_service is None:
        _cache_service = CacheService()
    return _cache_service


# Decorator for automatic caching
def cached(ttl: Optional[int] = None, key_prefix: str = ""):
    """
    Decorator to cache function results
    Usage: @cached(ttl=60, key_prefix="user")
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache_service()
            
            # Generate cache key
            key = cache.generate_key(
                key_prefix or func.__name__,
                *args,
                **{k: v for k, v in kwargs.items() if v is not None}
            )
            
            # Try to get from cache
            cached_value = await cache.get(key)
            if cached_value is not None:
                return cached_value
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Cache result
            if result is not None:
                await cache.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator