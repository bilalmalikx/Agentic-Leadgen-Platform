"""
Authentication Middleware
JWT and API Key authentication for protected routes
"""

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Optional, List, Set
import re

from app.core.security import decode_access_token, verify_api_key
from app.core.redis_client import cache_get
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware for JWT and API key validation
    """
    
    # Public paths that don't require authentication
    PUBLIC_PATHS: Set[str] = {
        "/health",
        "/ready",
        "/live",
        "/metrics",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/api/v1/health",
        "/"
    }
    
    # Path patterns that are public (regex)
    PUBLIC_PATTERNS: List[str] = [
        r"^/docs.*",
        r"^/redoc.*",
        r"^/openapi.*"
    ]
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.security = HTTPBearer(auto_error=False)
    
    async def dispatch(self, request: Request, call_next):
        """Process request and validate authentication"""
        
        # Check if path is public
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Try to authenticate
        user = await self._authenticate(request)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        # Store user in request state
        request.state.user = user
        request.state.user_id = user.get("user_id")
        
        # Check if user is active and has quota
        if not await self._check_user_status(user.get("user_id")):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive or suspended"
            )
        
        # Process request
        response = await call_next(request)
        
        return response
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)"""
        # Exact match
        if path in self.PUBLIC_PATHS:
            return True
        
        # Pattern match
        for pattern in self.PUBLIC_PATTERNS:
            if re.match(pattern, path):
                return True
        
        return False
    
    async def _authenticate(self, request: Request) -> Optional[dict]:
        """Authenticate user via JWT or API key"""
        
        # Try JWT Bearer token first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            user = await self._authenticate_jwt(token)
            if user:
                return user
        
        # Try API key
        api_key = request.headers.get("X-API-Key")
        if api_key:
            user = await self._authenticate_api_key(api_key)
            if user:
                return user
        
        return None
    
    async def _authenticate_jwt(self, token: str) -> Optional[dict]:
        """Authenticate using JWT token"""
        try:
            payload = decode_access_token(token)
            
            # Check if token is blacklisted
            blacklist_key = f"token:blacklist:{token}"
            if await cache_get(blacklist_key):
                logger.warning(f"Blacklisted token used")
                return None
            
            return {
                "user_id": payload.get("sub"),
                "email": payload.get("email"),
                "role": payload.get("role", "user"),
                "auth_type": "jwt"
            }
        except Exception as e:
            logger.debug(f"JWT authentication failed: {e}")
            return None
    
    async def _authenticate_api_key(self, api_key: str) -> Optional[dict]:
        """Authenticate using API key"""
        try:
            from app.services.user_service import get_user_by_api_key
            
            # Get user by API key
            user = await get_user_by_api_key(api_key)
            
            if not user:
                logger.warning(f"Invalid API key used")
                return None
            
            # Check if API key is expired
            if user.get("api_key_expires_at"):
                from datetime import datetime
                if datetime.utcnow() > user["api_key_expires_at"]:
                    logger.warning(f"Expired API key used for user {user['id']}")
                    return None
            
            return {
                "user_id": user["id"],
                "email": user["email"],
                "role": user.get("role", "user"),
                "auth_type": "api_key",
                "api_key_id": user.get("api_key_id")
            }
        except Exception as e:
            logger.debug(f"API key authentication failed: {e}")
            return None
    
    async def _check_user_status(self, user_id: str) -> bool:
        """Check if user account is active"""
        if not user_id:
            return False
        
        try:
            from app.services.user_service import get_user_by_id
            
            user = await get_user_by_id(user_id)
            
            if not user:
                return False
            
            # Check status
            status = user.get("status", "active")
            return status == "active"
            
        except Exception as e:
            logger.error(f"Failed to check user status: {e}")
            return True  # Allow if can't check (fail open)