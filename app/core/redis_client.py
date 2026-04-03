"""
Redis Client for Caching, Rate Limiting, and Session Management
Supports connection pooling and automatic reconnection
"""

import redis.asyncio as redis
from typing import Optional, Any, Dict
import json
import logging
from functools import wraps

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global Redis connection pool
_redis_pool: Optional[redis.ConnectionPool] = None
_redis_client: Optional[redis.Redis] = None


async def init_redis() -> None:
    """
    Initialize Redis connection pool
    Creates connection pool and client
    """
    global _redis_pool, _redis_client
    
    try:
        # Parse Redis URL
        redis_url = settings.redis_url
        
        # Create connection pool
        _redis_pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=5,
            retry_on_timeout=True
        )
        
        # Create Redis client
        _redis_client = redis.Redis(
            connection_pool=_redis_pool,
            decode_responses=True
        )
        
        # Test connection
        await _redis_client.ping()
        logger.info("Redis connection pool created successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Redis: {e}")
        raise


async def close_redis() -> None:
    """
    Close Redis connection pool
    Cleanup on application shutdown
    """
    global _redis_pool, _redis_client
    if _redis_client:
        await _redis_client.close()
    if _redis_pool:
        await _redis_pool.disconnect()
    logger.info("Redis connection closed")


async def get_redis() -> redis.Redis:
    """
    Get Redis client instance
    Returns the global Redis client
    """
    global _redis_client
    if not _redis_client:
        await init_redis()
    return _redis_client


async def cache_get(key: str) -> Optional[Any]:
    """
    Get value from cache
    Returns deserialized JSON or None
    """
    try:
        client = await get_redis()
        value = await client.get(key)
        if value:
            return json.loads(value)
        return None
    except Exception as e:
        logger.error(f"Redis cache get error for key {key}: {e}")
        return None


async def cache_set(
    key: str,
    value: Any,
    ttl: Optional[int] = None
) -> bool:
    """
    Set value in cache with optional TTL
    Serializes to JSON
    """
    try:
        client = await get_redis()
        serialized = json.dumps(value, default=str)
        
        if ttl:
            await client.setex(key, ttl, serialized)
        else:
            await client.set(key, serialized)
        
        return True
    except Exception as e:
        logger.error(f"Redis cache set error for key {key}: {e}")
        return False


async def cache_delete(key: str) -> bool:
    """
    Delete key from cache
    """
    try:
        client = await get_redis()
        await client.delete(key)
        return True
    except Exception as e:
        logger.error(f"Redis cache delete error for key {key}: {e}")
        return False


async def cache_exists(key: str) -> bool:
    """
    Check if key exists in cache
    """
    try:
        client = await get_redis()
        return await client.exists(key) > 0
    except Exception as e:
        logger.error(f"Redis cache exists error for key {key}: {e}")
        return False


async def increment_counter(key: str, expire: Optional[int] = None) -> int:
    """
    Increment counter in Redis
    Used for rate limiting
    """
    try:
        client = await get_redis()
        count = await client.incr(key)
        
        if expire and count == 1:
            await client.expire(key, expire)
        
        return count
    except Exception as e:
        logger.error(f"Redis increment error for key {key}: {e}")
        return 0


async def get_redis_health() -> Dict[str, Any]:
    """
    Check Redis health
    Returns status and info
    """
    try:
        client = await get_redis()
        await client.ping()
        
        info = await client.info("server")
        
        return {
            "status": "healthy",
            "version": info.get("redis_version", "unknown"),
            "connected_clients": await client.client_count()
        }
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


# Decorator for caching function results
def cached(ttl: int = 300):
    """
    Decorator to cache function results in Redis
    Usage: @cached(ttl=60)
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__module__}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Try to get from cache
            cached_result = await cache_get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Call function
            result = await func(*args, **kwargs)
            
            # Store in cache
            await cache_set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator