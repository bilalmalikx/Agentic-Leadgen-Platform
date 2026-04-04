"""
Formatters
Data formatting functions for consistent output
"""

from typing import Any, Dict, List, Optional, Union
from datetime import datetime, date
import json

from app.core.constants import DATE_FORMAT, DATETIME_FORMAT, ISO_FORMAT


class Formatters:
    """Collection of formatting functions"""
    
    @staticmethod
    def format_datetime(dt: datetime, format_type: str = "iso") -> str:
        """Format datetime to string"""
        if not dt:
            return None
        
        if format_type == "iso":
            return dt.isoformat()
        elif format_type == "date":
            return dt.strftime(DATE_FORMAT)
        elif format_type == "datetime":
            return dt.strftime(DATETIME_FORMAT)
        else:
            return dt.isoformat()
    
    @staticmethod
    def format_date(date_obj: date, format_type: str = "iso") -> str:
        """Format date to string"""
        if not date_obj:
            return None
        
        if format_type == "iso":
            return date_obj.isoformat()
        else:
            return date_obj.strftime(DATE_FORMAT)
    
    @staticmethod
    def format_phone(phone: str) -> str:
        """Format phone number consistently"""
        if not phone:
            return None
        
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)
        
        # Format based on length
        if len(digits) == 10:
            return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
        elif len(digits) == 11 and digits[0] == '1':
            return f"+1 ({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
        else:
            return phone
    
    @staticmethod
    def format_name(first_name: str, last_name: str) -> str:
        """Format full name"""
        if not first_name and not last_name:
            return None
        
        if first_name and last_name:
            return f"{first_name} {last_name}"
        elif first_name:
            return first_name
        else:
            return last_name
    
    @staticmethod
    def format_currency(amount: Union[int, float], currency: str = "USD") -> str:
        """Format currency amount"""
        if amount is None:
            return None
        
        if currency == "USD":
            return f"${amount:,.2f}"
        elif currency == "EUR":
            return f"€{amount:,.2f}"
        elif currency == "GBP":
            return f"£{amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency}"
    
    @staticmethod
    def format_percentage(value: float, decimal_places: int = 2) -> str:
        """Format percentage"""
        if value is None:
            return None
        
        return f"{value:.{decimal_places}f}%"
    
    @staticmethod
    def format_score(score: int) -> str:
        """Format lead score"""
        if score is None:
            return "N/A"
        
        if score >= 80:
            return f"{score} (Hot)"
        elif score >= 60:
            return f"{score} (Warm)"
        elif score >= 40:
            return f"{score} (Cold)"
        else:
            return f"{score} (Unqualified)"
    
    @staticmethod
    def truncate(text: str, max_length: int = 100, suffix: str = "...") -> str:
        """Truncate text to maximum length"""
        if not text or len(text) <= max_length:
            return text
        
        return text[:max_length - len(suffix)] + suffix
    
    @staticmethod
    def slugify(text: str) -> str:
        """Convert text to slug (URL-friendly)"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Replace spaces with hyphens
        text = re.sub(r'\s+', '-', text)
        
        # Remove special characters
        text = re.sub(r'[^\w\-]', '', text)
        
        return text
    
    @staticmethod
    def to_json(data: Any, indent: int = 2) -> str:
        """Convert data to JSON string"""
        return json.dumps(data, default=str, indent=indent)
    
    @staticmethod
    def to_dict(obj: Any) -> Dict[str, Any]:
        """Convert object to dictionary"""
        if hasattr(obj, 'dict'):
            return obj.dict()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return {"value": obj}
    
    @staticmethod
    def mask_email(email: str) -> str:
        """Mask email address (e.g., j***@example.com)"""
        if not email or '@' not in email:
            return email
        
        local_part, domain = email.split('@', 1)
        
        if len(local_part) <= 2:
            masked_local = '*' * len(local_part)
        else:
            masked_local = local_part[0] + '*' * (len(local_part) - 2) + local_part[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def mask_phone(phone: str) -> str:
        """Mask phone number (e.g., ***-***-1234)"""
        if not phone:
            return phone
        
        digits = re.sub(r'\D', '', phone)
        
        if len(digits) >= 4:
            return '*' * (len(digits) - 4) + digits[-4:]
        else:
            return '*' * len(digits)


# Convenience functions
def format_datetime(dt: datetime) -> str:
    return Formatters.format_datetime(dt)


def truncate(text: str, max_length: int = 100) -> str:
    return Formatters.truncate(text, max_length)


def to_json(data: Any) -> str:
    return Formatters.to_json(data)


def mask_email(email: str) -> str:
    return Formatters.mask_email(email)