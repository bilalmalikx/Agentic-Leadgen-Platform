"""
Lead Validator Agent
Validates lead data quality, completeness, and format correctness
"""

from typing import List, Dict, Any, Optional, Tuple
import re
from email_validator import validate_email, EmailNotValidError

from app.core.logging import get_logger
from app.agents.base import BaseAgent, retry_on_failure

logger = get_logger(__name__)


class LeadValidatorAgent(BaseAgent):
    """
    Agent responsible for validating lead data
    Checks email format, phone numbers, URLs, data completeness
    """
    
    def __init__(self):
        super().__init__(name="lead_validator", version="1.0.0")
        
        # Validation patterns
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        self.phone_pattern = re.compile(r'^[\+]?[(]?[0-9]{1,4}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{4,10}$')
        self.url_pattern = re.compile(r'^https?:\/\/(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&\/=]*)$')
    
    @retry_on_failure(max_retries=2)
    async def process(self, lead: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single lead
        """
        self.log_step("validating_lead", {"email": lead.get("email")})
        
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
            "score": 100  # Start with perfect score, deduct for issues
        }
        
        # Validate email (required)
        email = lead.get("email", "")
        is_valid, error, score_deduction = self._validate_email(email)
        if not is_valid:
            validation_results["is_valid"] = False
            validation_results["errors"].append(error)
            validation_results["score"] -= score_deduction
        elif error:  # Warning
            validation_results["warnings"].append(error)
            validation_results["score"] -= score_deduction
        
        # Validate phone (optional)
        phone = lead.get("phone", "")
        if phone:
            is_valid, error, score_deduction = self._validate_phone(phone)
            if not is_valid:
                validation_results["warnings"].append(error)
                validation_results["score"] -= score_deduction
        
        # Validate LinkedIn URL (optional)
        linkedin_url = lead.get("linkedin_url", "")
        if linkedin_url:
            is_valid, error, score_deduction = self._validate_linkedin_url(linkedin_url)
            if not is_valid:
                validation_results["warnings"].append(error)
                validation_results["score"] -= score_deduction
        
        # Validate company website (optional)
        website = lead.get("company_website", "")
        if website:
            is_valid, error, score_deduction = self._validate_url(website)
            if not is_valid:
                validation_results["warnings"].append(error)
                validation_results["score"] -= score_deduction
        
        # Check data completeness
        completeness_score = self._check_completeness(lead)
        validation_results["score"] = max(0, validation_results["score"] - (100 - completeness_score))
        
        # Add validation results to lead
        lead["validation"] = validation_results
        lead["is_valid"] = validation_results["is_valid"]
        lead["validation_score"] = validation_results["score"]
        
        self.logger.info(
            f"Lead {lead.get('email')} validation: "
            f"valid={validation_results['is_valid']}, "
            f"score={validation_results['score']}"
        )
        
        return lead
    
    async def validate_batch(
        self,
        leads: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validate multiple leads in batch
        """
        self.logger.info(f"Validating batch of {len(leads)} leads")
        return await self.process_batch(leads)
    
    def _validate_email(self, email: str) -> Tuple[bool, Optional[str], int]:
        """
        Validate email format and deliverability
        Returns (is_valid, error_message, score_deduction)
        """
        if not email:
            return False, "Email is required", 100
        
        if len(email) > 255:
            return False, "Email too long (max 255 characters)", 50
        
        try:
            # Use email_validator library
            validated = validate_email(email, check_deliverability=False)
            return True, None, 0
        except EmailNotValidError as e:
            return False, str(e), 100
        
        # Check for disposable email domains
        disposable_domains = ["tempmail.com", "10minutemail.com", "guerrillamail.com"]
        domain = email.split("@")[-1].lower()
        if domain in disposable_domains:
            return True, f"Disposable email domain: {domain}", 30
        
        return True, None, 0
    
    def _validate_phone(self, phone: str) -> Tuple[bool, Optional[str], int]:
        """
        Validate phone number format
        """
        if not phone:
            return True, None, 0
        
        if not self.phone_pattern.match(phone):
            return False, f"Invalid phone format: {phone}", 20
        
        return True, None, 0
    
    def _validate_linkedin_url(self, url: str) -> Tuple[bool, Optional[str], int]:
        """
        Validate LinkedIn URL format
        """
        if not url:
            return True, None, 0
        
        if "linkedin.com" not in url:
            return False, f"Invalid LinkedIn URL: {url}", 20
        
        if not self.url_pattern.match(url):
            return False, f"Invalid URL format: {url}", 20
        
        return True, None, 0
    
    def _validate_url(self, url: str) -> Tuple[bool, Optional[str], int]:
        """
        Validate general URL format
        """
        if not url:
            return True, None, 0
        
        if not self.url_pattern.match(url):
            return False, f"Invalid URL format: {url}", 20
        
        return True, None, 0
    
    def _check_completeness(self, lead: Dict[str, Any]) -> int:
        """
        Check data completeness and return score (0-100)
        """
        fields = [
            ("email", 30),
            ("first_name", 10),
            ("last_name", 10),
            ("company_name", 20),
            ("job_title", 15),
            ("location", 10),
            ("linkedin_url", 5)
        ]
        
        score = 0
        for field, weight in fields:
            if lead.get(field):
                score += weight
        
        return score
    
    def get_invalid_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter and return only invalid leads
        """
        return [lead for lead in leads if not lead.get("is_valid", True)]
    
    def get_valid_leads(self, leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter and return only valid leads
        """
        return [lead for lead in leads if lead.get("is_valid", False)]


# Singleton instance
_validator_agent = None


def get_validator_agent() -> LeadValidatorAgent:
    """Get or create validator agent instance"""
    global _validator_agent
    if _validator_agent is None:
        _validator_agent = LeadValidatorAgent()
    return _validator_agent