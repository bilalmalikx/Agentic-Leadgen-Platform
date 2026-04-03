"""
Rate Limit Middleware
Enforces rate limiting per user and per IP
"""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Dict, Tuple
import time

from app.core.redis_client import increment_counter, cache_get, cache_set
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces rate limiting using token bucket algorithm
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        
        # Rate limit configuration
        self.per_user_limit = settings.rate_limit_per_user
        self.per_ip_limit = settings.rate_limit_per_ip
        self.window_seconds = settings.rate_limit_window_minutes * 60
    
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check endpoints
        if request.url.path in ["/health", "/ready", "/live", "/metrics"]:
            return await call_next(request)
        
        # Get identifiers
        user_id = self._get_user_id(request)
        client_ip = self._get_client_ip(request)
        
        # Check user rate limit (if authenticated)
        if user_id:
            is_allowed, retry_after = await self._check_rate_limit(
                f"ratelimit:user:{user_id}",
                self.per_user_limit
            )
            if not is_allowed:
                return self._rate_limit_response(retry_after, "User rate limit exceeded")
        
        # Check IP rate limit
        is_allowed, retry_after = await self._check_rate_limit(
            f"ratelimit:ip:{client_ip}",
            self.per_ip_limit
        )
        if not is_allowed:
            return self._rate_limit_response(retry_after, "IP rate limit exceeded")
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self.per_user_limit if user_id else self.per_ip_limit)
        response.headers["X-RateLimit-Remaining"] = str(await self._get_remaining(request))
        
        return response
    
    def _get_user_id(self, request: Request) -> str:
        """Extract user ID from request"""
        # Try to get from authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # In production, decode JWT to get user ID
            # For now, return None (IP-based limiting)
            pass
        
        # Try to get from API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # Hash API key for rate limiting
            import hashlib
            return hashlib.md5(api_key.encode()).hexdigest()[:16]
        
        return None
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address"""
        # Check for proxy headers
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    async def _check_rate_limit(self, key: str, limit: int) -> Tuple[bool, int]:
        """Check if request is within rate limit"""
        # Get current count
        count = await increment_counter(key, self.window_seconds)
        
        if count > limit:
            # Calculate retry after time
            ttl = await self._get_ttl(key)
            return False, ttl
        
        return True, 0
    
    async def _get_ttl(self, key: str) -> int:
        """Get TTL for rate limit key"""
        from app.core.redis_client import get_redis
        redis = await get_redis()
        ttl = await redis.ttl(key)
        return max(0, ttl)
    
    async def _get_remaining(self, request: Request) -> int:
        """Get remaining rate limit"""
        user_id = self._get_user_id(request)
        client_ip = self._get_client_ip(request)
        
        key = f"ratelimit:user:{user_id}" if user_id else f"ratelimit:ip:{client_ip}"
        limit = self.per_user_limit if user_id else self.per_ip_limit
        
        count = await cache_get(key)
        if count:
            return max(0, limit - int(count))
        return limit
    
    def _rate_limit_response(self, retry_after: int, message: str):
        """Return rate limit exceeded response"""
        from fastapi.responses import JSONResponse
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "success": False,
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": message,
                "retry_after": retry_after,
                "timestamp": time.time()
            },
            headers={"Retry-After": str(retry_after)}
        )