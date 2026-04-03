"""
Content Moderator Guardrail
Combines all content safety checks (PII, Toxicity, Compliance)
"""

from typing import Tuple, Optional, Dict, Any, List
from enum import Enum

from app.core.logging import get_logger
from app.guardrails.pii_detector import pii_detector
from app.guardrails.toxicity_filter import toxicity_filter
from app.guardrails.compliance_checker import compliance_checker

logger = get_logger(__name__)


class ModerationAction(Enum):
    """Actions to take based on moderation result"""
    ALLOW = "allow"
    BLOCK = "block"
    FLAG = "flag"
    MASK = "mask"


class ModerationResult:
    """Result of content moderation"""
    
    def __init__(
        self,
        is_allowed: bool,
        action: ModerationAction,
        reasons: List[str],
        masked_content: Optional[str] = None
    ):
        self.is_allowed = is_allowed
        self.action = action
        self.reasons = reasons
        self.masked_content = masked_content
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_allowed": self.is_allowed,
            "action": self.action.value,
            "reasons": self.reasons,
            "masked_content": self.masked_content
        }


class ContentModerator:
    """
    Comprehensive content moderator that checks:
    - PII (Personally Identifiable Information)
    - Toxicity (profanity, threats, harassment)
    - Compliance (GDPR, CCPA)
    """
    
    def __init__(self):
        self.pii_detector = pii_detector
        self.toxicity_filter = toxicity_filter
        self.compliance_checker = compliance_checker
    
    def moderate_input(self, text: str, context: str = "api") -> ModerationResult:
        """
        Moderate user input before processing
        """
        reasons = []
        
        # Check for PII (warn but don't block unless sensitive)
        has_pii = self.pii_detector.has_pii(text)
        if has_pii:
            reasons.append("contains_pii")
        
        # Check for toxicity (block if found)
        is_toxic, toxicity_reasons = self.toxicity_filter.check_toxicity(text)
        if is_toxic:
            reasons.extend(toxicity_reasons)
            return ModerationResult(
                is_allowed=False,
                action=ModerationAction.BLOCK,
                reasons=reasons
            )
        
        # Check compliance (GDPR requirements)
        is_compliant, compliance_reasons = self.compliance_checker.check_compliance(text)
        if not is_compliant:
            reasons.extend(compliance_reasons)
            return ModerationResult(
                is_allowed=False,
                action=ModerationAction.BLOCK,
                reasons=reasons
            )
        
        # Mask PII if present
        masked_content = None
        if has_pii:
            masked_content = self.pii_detector.mask_pii_in_text(text)
            action = ModerationAction.MASK
        else:
            action = ModerationAction.ALLOW
        
        return ModerationResult(
            is_allowed=True,
            action=action,
            reasons=reasons,
            masked_content=masked_content
        )
    
    def moderate_output(self, text: str, context: str = "api") -> ModerationResult:
        """
        Moderate output before sending to client
        """
        reasons = []
        
        # Always mask PII in output
        has_pii = self.pii_detector.has_pii(text)
        masked_content = self.pii_detector.mask_pii_in_text(text) if has_pii else text
        
        if has_pii:
            reasons.append("pii_masked")
        
        # Check toxicity (block if found)
        is_toxic, toxicity_reasons = self.toxicity_filter.check_toxicity(masked_content)
        if is_toxic:
            reasons.extend(toxicity_reasons)
            return ModerationResult(
                is_allowed=False,
                action=ModerationAction.BLOCK,
                reasons=reasons
            )
        
        return ModerationResult(
            is_allowed=True,
            action=ModerationAction.ALLOW if not has_pii else ModerationAction.MASK,
            reasons=reasons,
            masked_content=masked_content
        )
    
    def moderate_batch(
        self,
        texts: List[str],
        direction: str = "input"
    ) -> List[ModerationResult]:
        """
        Moderate multiple texts
        """
        results = []
        
        for text in texts:
            if direction == "input":
                result = self.moderate_input(text)
            else:
                result = self.moderate_output(text)
            results.append(result)
        
        return results
    
    def get_safe_content(self, text: str, context: str = "api") -> str:
        """
        Get safe version of content (masked, filtered)
        """
        result = self.moderate_output(text, context)
        
        if result.masked_content:
            return result.masked_content
        
        if not result.is_allowed:
            return "[CONTENT BLOCKED]"
        
        return text


# Singleton instance
content_moderator = ContentModerator()


def moderate(text: str, direction: str = "input") -> ModerationResult:
    """Quick function to moderate content"""
    if direction == "input":
        return content_moderator.moderate_input(text)
    return content_moderator.moderate_output(text)