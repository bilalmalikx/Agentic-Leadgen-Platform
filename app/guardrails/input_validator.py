"""
Input Validator Guardrail
Validates all inputs before processing
Prevents injection attacks and malformed data
"""

import re
from typing import Tuple, Optional, List, Dict, Any
from email_validator import validate_email, EmailNotValidError
from urllib.parse import urlparse

from app.core.logging import get_logger

logger = get_logger(__name__)


class InputValidator:
    """
    Validates all user inputs before processing
    Guardrail at API entry point
    """
    
    # Patterns for validation
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    PHONE_PATTERN = re.compile(r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,6}$')
    URL_PATTERN = re.compile(r'^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$')
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bSELECT\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bUNION\b.*\bSELECT\b)",
        r"(--)",
        r"(;.*--)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)"
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script",
        r"javascript:",
        r"onclick=",
        r"onload=",
        r"onerror=",
        r"<iframe",
        r"<object",
        r"<embed"
    ]
    
    def validate_email(self, email: str) -> Tuple[bool, Optional[str]]:
        """
        Validate email address format
        Returns (is_valid, error_message)
        """
        if not email:
            return False, "Email is required"
        
        if len(email) > 255:
            return False, "Email too long (max 255 characters)"
        
        try:
            # Use email_validator library for thorough validation
            validated = validate_email(email, check_deliverability=False)
            return True, None
        except EmailNotValidError as e:
            return False, str(e)
    
    def validate_phone(self, phone: str) -> Tuple[bool, Optional[str]]:
        """
        Validate phone number format
        """
        if not phone:
            return True, None  # Phone is optional
        
        if not self.PHONE_PATTERN.match(phone):
            return False, "Invalid phone number format"
        
        return True, None
    
    def validate_url(self, url: str) -> Tuple[bool, Optional[str]]:
        """
        Validate URL format
        """
        if not url:
            return True, None  # URL is optional
        
        if len(url) > 2000:
            return False, "URL too long (max 2000 characters)"
        
        if not self.URL_PATTERN.match(url):
            return False, "Invalid URL format"
        
        # Parse URL to check components
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return False, "Invalid URL: missing scheme or domain"
            
            # Block dangerous schemes
            dangerous_schemes = ['file', 'ftp', 'data', 'javascript']
            if parsed.scheme in dangerous_schemes:
                return False, f"Dangerous URL scheme: {parsed.scheme}"
            
            return True, None
        except Exception:
            return False, "Invalid URL"
    
    def validate_text(
        self,
        text: str,
        max_length: int = 1000,
        allow_empty: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate text input (no SQL injection, no XSS)
        """
        if not text:
            if allow_empty:
                return True, None
            return False, "Text is required"
        
        if len(text) > max_length:
            return False, f"Text too long (max {max_length} characters)"
        
        # Check for SQL injection
        for pattern in self.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential SQL injection detected: {text[:100]}")
                return False, "Invalid characters in input"
        
        # Check for XSS
        for pattern in self.XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning(f"Potential XSS detected: {text[:100]}")
                return False, "Invalid characters in input"
        
        return True, None
    
    def validate_name(self, name: str) -> Tuple[bool, Optional[str]]:
        """
        Validate person/company name
        """
        if not name:
            return False, "Name is required"
        
        if len(name) > 255:
            return False, "Name too long (max 255 characters)"
        
        # Allow letters, spaces, dots, hyphens, apostrophes
        if not re.match(r"^[a-zA-Z\s\.\-'àâäéèêëîïôöùûüçÀÂÄÉÈÊËÎÏÔÖÙÛÜÇ]+$", name):
            return False, "Name contains invalid characters"
        
        return True, None
    
    def validate_query(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Validate search query
        """
        if not query:
            return False, "Query is required"
        
        if len(query) > 500:
            return False, "Query too long (max 500 characters)"
        
        # Check for dangerous patterns
        dangerous = [';', 'DROP', 'DELETE', 'INSERT', 'UPDATE', '--', '/*', '*/']
        for item in dangerous:
            if item.lower() in query.lower():
                return False, f"Query contains invalid characters: {item}"
        
        return True, None
    
    def sanitize_input(self, text: str) -> str:
        """
        Sanitize input by removing dangerous characters
        """
        if not text:
            return text
        
        # Remove SQL injection patterns
        for pattern in self.SQL_INJECTION_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Remove XSS patterns
        for pattern in self.XSS_PATTERNS:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # Escape HTML
        html_escape_table = {
            "&": "&amp;",
            '"': "&quot;",
            "'": "&apos;",
            ">": "&gt;",
            "<": "&lt;",
        }
        text = "".join(html_escape_table.get(c, c) for c in text)
        
        return text.strip()
    
    def validate_campaign_inputs(self, data: Dict[str, Any]) -> List[str]:
        """
        Validate all campaign inputs
        Returns list of validation errors
        """
        errors = []
        
        # Validate name
        if 'name' in data:
            is_valid, error = self.validate_name(data['name'])
            if not is_valid:
                errors.append(f"name: {error}")
        
        # Validate query
        if 'query' in data:
            is_valid, error = self.validate_query(data['query'])
            if not is_valid:
                errors.append(f"query: {error}")
        
        # Validate sources
        if 'sources' in data:
            valid_sources = ['linkedin', 'twitter', 'crunchbase', 'company_website']
            for source in data['sources']:
                if source not in valid_sources:
                    errors.append(f"source: {source} is not valid")
        
        # Validate webhook URL
        if 'webhook_url' in data and data['webhook_url']:
            is_valid, error = self.validate_url(data['webhook_url'])
            if not is_valid:
                errors.append(f"webhook_url: {error}")
        
        return errors