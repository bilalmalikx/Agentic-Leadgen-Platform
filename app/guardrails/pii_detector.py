"""
PII Detector Guardrail
Detects and masks Personally Identifiable Information
For compliance with GDPR, CCPA, etc.
"""

import re
from typing import List, Tuple, Dict, Any, Optional
from enum import Enum

from app.core.logging import get_logger

logger = get_logger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected"""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    BANK_ACCOUNT = "bank_account"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"


class PIIDetector:
    """
    Detects and masks PII in text and JSON data
    Used for compliance and data protection
    """
    
    # Patterns for PII detection
    PATTERNS = {
        PIIType.EMAIL: re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        PIIType.PHONE: re.compile(r'\b[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{4,10}\b'),
        PIIType.SSN: re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        PIIType.CREDIT_CARD: re.compile(r'\b(?:\d[ -]*?){13,16}\b'),
        PIIType.IP_ADDRESS: re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
        PIIType.DATE_OF_BIRTH: re.compile(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'),
    }
    
    # Sensitive field names (case-insensitive)
    SENSITIVE_FIELDS = [
        'password', 'token', 'secret', 'key', 'api_key', 'auth',
        'ssn', 'social_security', 'credit_card', 'card_number',
        'bank_account', 'routing_number', 'passport', 'license'
    ]
    
    def __init__(self, mask_character: str = "*", mask_length: int = 4):
        self.mask_character = mask_character
        self.mask_length = mask_length
    
    def detect_pii(self, text: str) -> List[Tuple[PIIType, str, int, int]]:
        """
        Detect PII in text
        Returns list of (type, matched_text, start_pos, end_pos)
        """
        detections = []
        
        for pii_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(text):
                detections.append((
                    pii_type,
                    match.group(),
                    match.start(),
                    match.end()
                ))
        
        return detections
    
    def mask_pii_in_text(self, text: str) -> str:
        """
        Mask all PII in text
        Replaces detected PII with mask characters
        """
        if not text:
            return text
        
        detections = self.detect_pii(text)
        
        # Sort by start position (reverse to not affect indices)
        detections.sort(key=lambda x: x[2], reverse=True)
        
        masked_text = text
        for pii_type, matched_text, start, end in detections:
            # Keep first and last characters, mask the middle
            if len(matched_text) > self.mask_length:
                masked_part = (
                    matched_text[0] +
                    self.mask_character * min(self.mask_length, len(matched_text) - 2) +
                    matched_text[-1]
                )
            else:
                masked_part = self.mask_character * len(matched_text)
            
            masked_text = masked_text[:start] + masked_part + masked_text[end:]
        
        return masked_text
    
    def mask_pii_in_json(self, data: Any, depth: int = 0) -> Any:
        """
        Recursively mask PII in JSON data
        """
        if depth > 10:  # Prevent infinite recursion
            return data
        
        if isinstance(data, dict):
            masked_dict = {}
            for key, value in data.items():
                # Check if key is sensitive
                if key.lower() in self.SENSITIVE_FIELDS:
                    masked_dict[key] = self.mask_character * 8
                else:
                    masked_dict[key] = self.mask_pii_in_json(value, depth + 1)
            return masked_dict
        
        elif isinstance(data, list):
            return [self.mask_pii_in_json(item, depth + 1) for item in data]
        
        elif isinstance(data, str):
            return self.mask_pii_in_text(data)
        
        else:
            return data
    
    def has_pii(self, text: str) -> bool:
        """Check if text contains PII"""
        return len(self.detect_pii(text)) > 0
    
    def redact_sensitive_fields(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Redact sensitive fields from dictionary
        """
        redacted = data.copy()
        
        for field in self.SENSITIVE_FIELDS:
            if field in redacted:
                redacted[field] = self.mask_character * 8
            
            # Check nested fields
            for key in list(redacted.keys()):
                if field in key.lower():
                    redacted[key] = self.mask_character * 8
        
        return redacted
    
    def get_pii_report(self, text: str) -> Dict[str, Any]:
        """
        Get detailed PII report for text
        """
        detections = self.detect_pii(text)
        
        pii_by_type = {}
        for pii_type, matched_text, _, _ in detections:
            if pii_type.value not in pii_by_type:
                pii_by_type[pii_type.value] = []
            pii_by_type[pii_type.value].append(matched_text)
        
        return {
            "has_pii": len(detections) > 0,
            "total_detections": len(detections),
            "pii_by_type": pii_by_type,
            "masked_text": self.mask_pii_in_text(text) if detections else text
        }
    
    def validate_no_pii(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate that text contains no PII
        Returns (is_valid, error_message)
        """
        if self.has_pii(text):
            pii_types = set(pii_type.value for pii_type, _, _, _ in self.detect_pii(text))
            return False, f"Text contains PII: {', '.join(pii_types)}"
        return True, None


# Singleton instance
pii_detector = PIIDetector()


def mask_pii(data: Any) -> Any:
    """Quick function to mask PII in any data"""
    return pii_detector.mask_pii_in_json(data)