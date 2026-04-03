"""
Global Error Handler
Handles all exceptions and returns consistent error responses
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Union, Dict, Any
import traceback
import time

from app.core.logging import get_logger
from app.core.exceptions import (
    AppException,
    NotFoundException,
    ValidationException,
    AuthenticationException,
    RateLimitException,
    ConflictException
)

logger = get_logger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware that catches all exceptions and returns formatted responses
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            return await self.handle_exception(request, exc)
    
    async def handle_exception(self, request: Request, exc: Exception) -> JSONResponse:
        """Handle different types of exceptions"""
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Log error with stack trace
        logger.error(
            f"Unhandled exception: {str(exc)}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
                "error": str(exc),
                "traceback": traceback.format_exc()
            }
        )
        
        # Map exception to response
        if isinstance(exc, NotFoundException):
            return self._error_response(
                status_code=status.HTTP_404_NOT_FOUND,
                error_code="NOT_FOUND",
                message=str(exc),
                request_id=request_id
            )
        
        elif isinstance(exc, ValidationException):
            return self._error_response(
                status_code=status.HTTP_400_BAD_REQUEST,
                error_code="VALIDATION_ERROR",
                message=str(exc),
                details=exc.details if hasattr(exc, 'details') else None,
                request_id=request_id
            )
        
        elif isinstance(exc, AuthenticationException):
            return self._error_response(
                status_code=status.HTTP_401_UNAUTHORIZED,
                error_code="UNAUTHORIZED",
                message=str(exc),
                request_id=request_id
            )
        
        elif isinstance(exc, RateLimitException):
            return self._error_response(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                error_code="RATE_LIMIT_EXCEEDED",
                message=str(exc),
                request_id=request_id
            )
        
        elif isinstance(exc, ConflictException):
            return self._error_response(
                status_code=status.HTTP_409_CONFLICT,
                error_code="CONFLICT",
                message=str(exc),
                request_id=request_id
            )
        
        elif isinstance(exc, HTTPException):
            return self._error_response(
                status_code=exc.status_code,
                error_code="HTTP_ERROR",
                message=str(exc.detail),
                request_id=request_id
            )
        
        else:
            # Unknown error - don't expose details in production
            from app.core.config import settings
            error_message = str(exc) if settings.app_env == "development" else "Internal server error"
            
            return self._error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_code="INTERNAL_SERVER_ERROR",
                message=error_message,
                request_id=request_id,
                details={"traceback": traceback.format_exc()} if settings.app_env == "development" else None
            )
    
    def _error_response(
        self,
        status_code: int,
        error_code: str,
        message: str,
        request_id: str,
        details: Any = None
    ) -> JSONResponse:
        """Create standardized error response"""
        return JSONResponse(
            status_code=status_code,
            content={
                "success": False,
                "error_code": error_code,
                "message": message,
                "details": details,
                "request_id": request_id,
                "timestamp": time.time()
            }
        )


# Global exception handler for FastAPI (not middleware)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler registered in main.py"""
    handler = ErrorHandlerMiddleware(app=None)  # type: ignore
    return await handler.handle_exception(request, exc)