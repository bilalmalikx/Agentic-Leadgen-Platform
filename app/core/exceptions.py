"""
Custom Exceptions
Application-specific exception classes with error codes
"""

from typing import Optional, Any, Dict


class AppException(Exception):
    """Base exception for all application exceptions"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "ERR_000",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundException(AppException):
    """Resource not found exception"""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with identifier {identifier} not found",
            error_code="ERR_005",
            status_code=404,
            details={"resource": resource, "identifier": identifier}
        )


class ValidationException(AppException):
    """Input validation failed"""
    
    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="ERR_001",
            status_code=400,
            details={"field": field} if field else {}
        )


class AuthenticationException(AppException):
    """Authentication failed"""
    
    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            error_code="ERR_003",
            status_code=401
        )


class AuthorizationException(AppException):
    """User not authorized"""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_code="ERR_004",
            status_code=403
        )


class RateLimitException(AppException):
    """Rate limit exceeded"""
    
    def __init__(self, retry_after: int = 60):
        super().__init__(
            message=f"Rate limit exceeded. Try again in {retry_after} seconds",
            error_code="ERR_002",
            status_code=429,
            details={"retry_after": retry_after}
        )


class ConflictException(AppException):
    """Resource conflict (duplicate, etc.)"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="ERR_006",
            status_code=409
        )


class QuotaExceededException(AppException):
    """User quota exceeded"""
    
    def __init__(self, quota_type: str, current: int, max_allowed: int):
        super().__init__(
            message=f"{quota_type} quota exceeded: {current}/{max_allowed}",
            error_code="ERR_009",
            status_code=429,
            details={"quota_type": quota_type, "current": current, "max": max_allowed}
        )


class ServiceUnavailableException(AppException):
    """External service unavailable"""
    
    def __init__(self, service: str):
        super().__init__(
            message=f"Service {service} is temporarily unavailable",
            error_code="ERR_008",
            status_code=503,
            details={"service": service}
        )


class ScrapingException(AppException):
    """Scraping operation failed"""
    
    def __init__(self, source: str, reason: str):
        super().__init__(
            message=f"Failed to scrape {source}: {reason}",
            error_code="ERR_SCRAPE_001",
            status_code=500,
            details={"source": source, "reason": reason}
        )


class LLMException(AppException):
    """LLM operation failed"""
    
    def __init__(self, provider: str, reason: str):
        super().__init__(
            message=f"LLM provider {provider} failed: {reason}",
            error_code="ERR_LLM_001",
            status_code=500,
            details={"provider": provider, "reason": reason}
        )


class WebhookDeliveryException(AppException):
    """Webhook delivery failed"""
    
    def __init__(self, url: str, status_code: int, response: str):
        super().__init__(
            message=f"Webhook delivery to {url} failed with status {status_code}",
            error_code="ERR_WEBHOOK_001",
            status_code=500,
            details={"url": url, "status_code": status_code, "response": response[:500]}
        )