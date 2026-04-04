"""
Validators
Common validation functions for email, phone, URL, and data formats
"""

import re
from typing import Tuple, Optional, List, Any
from email_validator import validate_email, EmailNotValidError
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)


class Validators:
    """Collection of validation functions"""
    
    # Patterns
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{4,10}$')
    URL_PATTERN = re.compile(r'^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$')
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    
    @classmethod
    def validate_email(cls, email: str, check_deliverability: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Validate email address
        Returns (is_valid, error_message)
        """
        if not email:
            return False, "Email is required"
        
        if len(email) > 255:
            return False, "Email too long (max 255 characters)"
        
        try:
            validated = validate_email(email, check_deliverability=check_deliverability)
            return True, None
        except EmailNotValidError as e:
            return False, str(e)
    
    @classmethod
    def validate_phone(cls, phone: str) -> Tuple[bool, Optional[str]]:
        """Validate phone number"""
        if not phone:
            return True, None
        
        if not cls.PHONE_PATTERN.match(phone):
            return False, "Invalid phone number format"
        
        return True, None
    
    @classmethod
    def validate_url(cls, url: str, require_https: bool = False) -> Tuple[bool, Optional[str]]:
        """Validate URL"""
        if not url:
            return True, None
        
        if len(url) > 2000:
            return False, "URL too long (max 2000 characters)"
        
        if not cls.URL_PATTERN.match(url):
            return False, "Invalid URL format"
        
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL: missing scheme or domain"
            
            if require_https and parsed.scheme != "https":
                return False, "HTTPS is required"
            
            # Block dangerous schemes
            dangerous_schemes = ['file', 'ftp', 'data', 'javascript']
            if parsed.scheme in dangerous_schemes:
                return False, f"Dangerous URL scheme: {parsed.scheme}"
            
            return True, None
        except Exception:
            return False, "Invalid URL"
    
    @classmethod
    def validate_uuid(cls, uuid_string: str) -> bool:
        """Validate UUID format"""
        return bool(cls.UUID_PATTERN.match(uuid_string))
    
    @classmethod
    def validate_text(
        cls,
        text: str,
        min_length: int = 1,
        max_length: int = 1000,
        allow_empty: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """Validate text input"""
        if not text:
            if allow_empty:
                return True, None
            return False, "Text is required"
        
        if len(text) < min_length:
            return False, f"Text too short (min {min_length} characters)"
        
        if len(text) > max_length:
            return False, f"Text too long (max {max_length} characters)"
        
        return True, None
    
    @classmethod
    def validate_name(cls, name: str) -> Tuple[bool, Optional[str]]:
        """Validate person/company name"""
        if not name:
            return False, "Name is required"
        
        if len(name) > 255:
            return False, "Name too long (max 255 characters)"
        
        # Allow letters, spaces, dots, hyphens, apostrophes
        if not re.match(r"^[a-zA-Z\s\.\-'àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]+$", name):
            return False, "Name contains invalid characters"
        
        return True, None
    
    @classmethod
    def validate_score(cls, score: int) -> Tuple[bool, Optional[str]]:
        """Validate lead score (0-100)"""
        if not isinstance(score, int):
            return False, "Score must be an integer"
        
        if score < 0 or score > 100:
            return False, "Score must be between 0 and 100"
        
        return True, None
    
    @classmethod
    def validate_date(cls, date_string: str) -> Tuple[bool, Optional[str]]:
        """Validate date format (ISO format)"""
        try:
            from datetime import datetime
            datetime.fromisoformat(date_string)
            return True, None
        except ValueError:
            return False, "Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"
    
    @classmethod
    def validate_json(cls, json_string: str) -> Tuple[bool, Optional[str]]:
        """Validate JSON string"""
        import json
        try:
            json.loads(json_string)
            return True, None
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
    
    @classmethod
    def sanitize_input(cls, text: str) -> str:
        """Sanitize input by removing dangerous characters"""
        if not text:
            return text
        
        # Remove SQL injection patterns
        sql_patterns = [r"(\bSELECT\b.*\bFROM\b)", r"(\bINSERT\b.*\bINTO\b)", r"(\bDROP\b.*\bTABLE\b)", r"(--)", r"(;.*--)"]
        for pattern in sql_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove XSS patterns
        xss_patterns = [r"<script", r"javascript:", r"onclick=", r"onload=", r"<iframe"]
        for pattern in xss_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()


# Convenience functions
def is_valid_email(email: str) -> bool:
    """Quick email validation"""
    is_valid, _ = Validators.validate_email(email)
    return is_valid


def is_valid_url(url: str) -> bool:
    """Quick URL validation"""
    is_valid, _ = Validators.validate_url(url)
    return is_valid


def is_valid_uuid(uuid_string: str) -> bool:
    """Quick UUID validation"""
    return Validators.validate_uuid(uuid_string)


def sanitize(text: str) -> str:
    """Quick input sanitization"""
    return Validators.sanitize_input(text)