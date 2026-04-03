"""
Output Filter Guardrail
Filters sensitive information from API responses
"""

from typing import Any, Dict, List, Optional, Union
import re

from app.core.logging import get_logger
from app.guardrails.pii_detector import PIIDetector

logger = get_logger(__name__)


class OutputFilter:
    """
    Filters and sanitizes output data before sending to client
    Removes sensitive fields, masks PII, and applies content policies
    """
    
    # Sensitive field names (case-insensitive)
    SENSITIVE_FIELDS = [
        "password", "token", "secret", "api_key", "api_secret",
        "private_key", "access_token", "refresh_token", "authorization",
        "credit_card", "card_number", "cvv", "ssn", "social_security",
        "bank_account", "routing_number", "internal_ip", "database_url"
    ]
    
    # Fields to always keep (override)
    SAFE_FIELDS = [
        "id", "email", "name", "status", "created_at", "updated_at"
    ]
    
    def __init__(self):
        self.pii_detector = PIIDetector()
    
    def filter_response(
        self,
        data: Any,
        remove_sensitive_fields: bool = True,
        mask_pii: bool = True,
        max_depth: int = 10
    ) -> Any:
        """
        Filter response data recursively
        """
        if max_depth <= 0:
            return data
        
        if isinstance(data, dict):
            return self._filter_dict(
                data,
                remove_sensitive_fields,
                mask_pii,
                max_depth - 1
            )
        elif isinstance(data, list):
            return [
                self.filter_response(
                    item,
                    remove_sensitive_fields,
                    mask_pii,
                    max_depth - 1
                )
                for item in data
            ]
        elif isinstance(data, str):
            if mask_pii:
                return self.pii_detector.mask_pii_in_text(data)
            return data
        else:
            return data
    
    def _filter_dict(
        self,
        data: Dict[str, Any],
        remove_sensitive: bool,
        mask_pii: bool,
        max_depth: int
    ) -> Dict[str, Any]:
        """Filter dictionary recursively"""
        filtered = {}
        
        for key, value in data.items():
            # Check if field should be removed
            if remove_sensitive and self._is_sensitive_field(key):
                filtered[key] = "[REDACTED]"
                continue
            
            # Check if field should be safe (always show)
            if key in self.SAFE_FIELDS:
                filtered[key] = self.filter_response(
                    value, remove_sensitive, mask_pii, max_depth - 1
                )
                continue
            
            # Process value
            if isinstance(value, dict):
                filtered[key] = self._filter_dict(
                    value, remove_sensitive, mask_pii, max_depth - 1
                )
            elif isinstance(value, list):
                filtered[key] = [
                    self.filter_response(
                        item, remove_sensitive, mask_pii, max_depth - 1
                    )
                    for item in value
                ]
            elif isinstance(value, str) and mask_pii:
                filtered[key] = self.pii_detector.mask_pii_in_text(value)
            else:
                filtered[key] = value
        
        return filtered
    
    def _is_sensitive_field(self, field_name: str) -> bool:
        """Check if field name indicates sensitive data"""
        field_lower = field_name.lower()
        
        for sensitive in self.SENSITIVE_FIELDS:
            if sensitive in field_lower:
                return True
        
        return False
    
    def filter_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Filter sensitive information from headers"""
        filtered = {}
        
        sensitive_headers = ["authorization", "cookie", "set-cookie", "x-api-key"]
        
        for key, value in headers.items():
            if key.lower() in sensitive_headers:
                filtered[key] = "[REDACTED]"
            else:
                filtered[key] = value
        
        return filtered
    
    def filter_log(self, log_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter log data - more aggressive filtering for logs
        """
        # Always remove sensitive fields from logs
        return self.filter_response(
            log_data,
            remove_sensitive_fields=True,
            mask_pii=True,
            max_depth=5
        )
    
    def get_safe_response(self, data: Any) -> Any:
        """
        Get maximally safe response (remove all sensitive, mask all PII)
        """
        return self.filter_response(
            data,
            remove_sensitive_fields=True,
            mask_pii=True
        )


# Singleton instance
output_filter = OutputFilter()


def filter_output(data: Any) -> Any:
    """Quick function to filter output"""
    return output_filter.filter_response(data)