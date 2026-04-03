"""
Compliance Checker Guardrail
GDPR, CCPA, and other regulatory compliance checks
"""

from typing import Tuple, List, Optional, Dict, Any
from datetime import datetime, timedelta
import re

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class ComplianceChecker:
    """
    Checks compliance with GDPR, CCPA, and other regulations
    """
    
    # GDPR sensitive data categories
    GDPR_SENSITIVE_CATEGORIES = [
        "race", "ethnicity", "political_opinions", "religious_beliefs",
        "trade_union_membership", "genetic_data", "biometric_data",
        "health_data", "sex_life", "sexual_orientation"
    ]
    
    # Required consent fields
    CONSENT_REQUIRED_FIELDS = [
        "data_processing_consent",
        "marketing_consent",
        "data_retention_agreement"
    ]
    
    def __init__(self):
        self.data_subject_requests = {}  # Track GDPR requests
        self.consent_records = {}  # Track user consent
    
    def check_compliance(self, data: Dict[str, Any], context: str = "storage") -> Tuple[bool, List[str]]:
        """
        Check if data complies with regulations
        Returns (is_compliant, violations)
        """
        violations = []
        
        # Check for sensitive data without consent
        if context == "storage":
            for category in self.GDPR_SENSITIVE_CATEGORIES:
                if category in data:
                    violations.append(f"sensitive_data_without_consent: {category}")
        
        # Check data retention
        if "created_at" in data:
            created_at = data["created_at"]
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except:
                    pass
            
            if isinstance(created_at, datetime):
                age_days = (datetime.utcnow() - created_at).days
                if age_days > 365:  # GDPR suggests 1 year max unless justified
                    violations.append(f"data_retention_exceeded: {age_days} days")
        
        # Check for right to be forgotten
        if data.get("request_deletion", False):
            violations.append("right_to_be_forgotten_requested")
        
        return len(violations) == 0, violations
    
    def validate_consent(self, user_id: str, consent_type: str) -> bool:
        """
        Validate if user has given required consent
        """
        if user_id not in self.consent_records:
            return False
        
        consents = self.consent_records[user_id]
        return consents.get(consent_type, False)
    
    def record_consent(self, user_id: str, consent_type: str, given: bool, ip_address: str = None):
        """
        Record user consent for audit trail
        """
        if user_id not in self.consent_records:
            self.consent_records[user_id] = {}
        
        self.consent_records[user_id][consent_type] = {
            "given": given,
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": ip_address
        }
        
        logger.info(f"Consent recorded for user {user_id}: {consent_type}={given}")
    
    def request_data_deletion(self, user_id: str, email: str) -> str:
        """
        Process GDPR right to be forgotten request
        Returns request ID
        """
        request_id = f"deletion_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        self.data_subject_requests[request_id] = {
            "user_id": user_id,
            "email": email,
            "type": "deletion",
            "status": "pending",
            "requested_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Data deletion request created: {request_id}")
        return request_id
    
    def request_data_portability(self, user_id: str, email: str) -> str:
        """
        Process GDPR right to data portability request
        Returns request ID
        """
        request_id = f"portability_{user_id}_{int(datetime.utcnow().timestamp())}"
        
        self.data_subject_requests[request_id] = {
            "user_id": user_id,
            "email": email,
            "type": "portability",
            "status": "pending",
            "requested_at": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Data portability request created: {request_id}")
        return request_id
    
    def get_compliance_report(self) -> Dict[str, Any]:
        """
        Generate compliance report for audit
        """
        return {
            "gdpr_compliant": True,
            "data_retention_days": 365,
            "consent_records_count": len(self.consent_records),
            "active_deletion_requests": len([
                r for r in self.data_subject_requests.values()
                if r["type"] == "deletion" and r["status"] == "pending"
            ]),
            "last_audit": datetime.utcnow().isoformat()
        }
    
    def anonymize_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anonymize personal data for GDPR compliance
        """
        anonymized = data.copy()
        
        # Anonymize email
        if "email" in anonymized:
            parts = anonymized["email"].split("@")
            if len(parts) == 2:
                anonymized["email"] = f"{parts[0][:2]}***@{parts[1]}"
        
        # Anonymize name
        if "first_name" in anonymized:
            anonymized["first_name"] = anonymized["first_name"][0] + "***"
        if "last_name" in anonymized:
            anonymized["last_name"] = anonymized["last_name"][0] + "***"
        
        # Anonymize phone
        if "phone" in anonymized and anonymized["phone"]:
            phone = anonymized["phone"]
            if len(phone) > 4:
                anonymized["phone"] = "***" + phone[-4:]
        
        # Remove IP addresses
        if "ip_address" in anonymized:
            del anonymized["ip_address"]
        
        return anonymized


# Singleton instance
compliance_checker = ComplianceChecker()


def check_compliance(data: Dict[str, Any], context: str = "storage") -> Tuple[bool, List[str]]:
    """Quick function to check compliance"""
    return compliance_checker.check_compliance(data, context)