"""
Toxicity Filter Guardrail
Detects and blocks toxic, offensive, or inappropriate content
"""

from typing import Tuple, List, Dict, Any, Optional
import re

from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class ToxicityFilter:
    """
    Filters toxic and inappropriate content from inputs and outputs
    """
    
    # Profanity patterns (basic - in production use better library)
    PROFANITY_PATTERNS = [
        r'\b(fuck|shit|asshole|bitch|cunt|dick|pussy)\b',
        r'\b(nigger|faggot|retard|tranny)\b',
        r'\b(kill\s+yourself|die\s+slow|rape)\b',
        r'\b(hate\s+speech|white\s+power|nazi)\b',
    ]
    
    # Threat patterns
    THREAT_PATTERNS = [
        r'\b(kill|murder|shoot|bomb|attack)\s+(you|them|everyone)\b',
        r'\b(destroy|ruin|crush)\s+(your|their)\s+(life|business|career)\b',
    ]
    
    # Harassment patterns
    HARASSMENT_PATTERNS = [
        r'\b(stalk|follow|track)\s+(you|them)\b',
        r'\b(harass|bully|intimidate)\b',
    ]
    
    def __init__(self):
        self.compiled_profanity = [re.compile(p, re.IGNORECASE) for p in self.PROFANITY_PATTERNS]
        self.compiled_threats = [re.compile(p, re.IGNORECASE) for p in self.THREAT_PATTERNS]
        self.compiled_harassment = [re.compile(p, re.IGNORECASE) for p in self.HARASSMENT_PATTERNS]
    
    def check_toxicity(self, text: str) -> Tuple[bool, List[str]]:
        """
        Check if text contains toxic content
        Returns (is_toxic, reasons)
        """
        if not text:
            return False, []
        
        reasons = []
        
        # Check profanity
        for pattern in self.compiled_profanity:
            if pattern.search(text):
                reasons.append("contains_profanity")
                break
        
        # Check threats
        for pattern in self.compiled_threats:
            if pattern.search(text):
                reasons.append("contains_threats")
                break
        
        # Check harassment
        for pattern in self.compiled_harassment:
            if pattern.search(text):
                reasons.append("contains_harassment")
                break
        
        return len(reasons) > 0, reasons
    
    def is_safe(self, text: str) -> bool:
        """Check if text is safe (not toxic)"""
        is_toxic, _ = self.check_toxicity(text)
        return not is_toxic
    
    def filter_toxic_content(self, text: str, replacement: str = "[FILTERED]") -> str:
        """
        Filter toxic content by replacing with placeholder
        """
        if not text:
            return text
        
        filtered_text = text
        
        # Replace profanity
        for pattern in self.compiled_profanity:
            filtered_text = pattern.sub(replacement, filtered_text)
        
        # Replace threats
        for pattern in self.compiled_threats:
            filtered_text = pattern.sub(replacement, filtered_text)
        
        # Replace harassment
        for pattern in self.compiled_harassment:
            filtered_text = pattern.sub(replacement, filtered_text)
        
        return filtered_text
    
    def validate_input(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Validate input for toxicity
        Returns (is_valid, error_message)
        """
        is_toxic, reasons = self.check_toxicity(text)
        
        if is_toxic:
            return False, f"Input contains inappropriate content: {', '.join(reasons)}"
        
        return True, None
    
    def check_batch(self, texts: List[str]) -> Dict[str, Any]:
        """
        Check multiple texts for toxicity
        """
        results = []
        toxic_count = 0
        
        for text in texts:
            is_toxic, reasons = self.check_toxicity(text)
            results.append({
                "text_preview": text[:100],
                "is_toxic": is_toxic,
                "reasons": reasons
            })
            if is_toxic:
                toxic_count += 1
        
        return {
            "total": len(texts),
            "toxic_count": toxic_count,
            "safe_count": len(texts) - toxic_count,
            "results": results
        }


# Singleton instance
toxicity_filter = ToxicityFilter()


def validate_content(text: str) -> Tuple[bool, Optional[str]]:
    """Quick function to validate content safety"""
    return toxicity_filter.validate_input(text)