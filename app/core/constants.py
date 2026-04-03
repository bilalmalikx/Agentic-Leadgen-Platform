"""
Application Constants
Centralized constants used across the application
"""

from enum import Enum
from typing import Dict, Any

# ============================================
# API Constants
# ============================================

API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"

# Rate Limit Headers
RATE_LIMIT_HEADER = "X-RateLimit-Limit"
RATE_LIMIT_REMAINING_HEADER = "X-RateLimit-Remaining"
RATE_LIMIT_RESET_HEADER = "X-RateLimit-Reset"
REQUEST_ID_HEADER = "X-Request-ID"

# ============================================
# Cache Keys
# ============================================

CACHE_KEY_LEAD = "lead:{}"
CACHE_KEY_CAMPAIGN = "campaign:{}"
CACHE_KEY_USER = "user:{}"
CACHE_KEY_LEAD_LIST = "leads:campaign:{}:page:{}"
CACHE_KEY_API_KEY = "apikey:{}"
CACHE_KEY_RATE_LIMIT = "ratelimit:{}:{}"

# Cache TTLs (seconds)
CACHE_TTL_SHORT = 60          # 1 minute
CACHE_TTL_MEDIUM = 300        # 5 minutes
CACHE_TTL_LONG = 3600         # 1 hour
CACHE_TTL_DAY = 86400         # 24 hours

# ============================================
# Queue Names
# ============================================

QUEUE_HIGH_PRIORITY = "high_priority"
QUEUE_DEFAULT = "default"
QUEUE_LOW_PRIORITY = "low_priority"
QUEUE_SCRAPING = "scraping"
QUEUE_EMAIL = "email"

# ============================================
# Lead Scoring Weights
# ============================================

SCORING_WEIGHTS: Dict[str, float] = {
    "job_title_match": 0.30,      # 30%
    "company_relevance": 0.25,     # 25%
    "social_activity": 0.20,       # 20%
    "company_size": 0.15,          # 15%
    "location_match": 0.10,        # 10%
}

# Job title priority mapping
JOB_TITLE_PRIORITY: Dict[str, int] = {
    "ceo": 100,
    "founder": 100,
    "cto": 95,
    "chief technology officer": 95,
    "vp engineering": 90,
    "director engineering": 85,
    "head of engineering": 85,
    "engineering manager": 75,
    "product manager": 70,
    "senior engineer": 60,
    "software engineer": 50,
}

# ============================================
# Pagination
# ============================================

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_PAGE = 1

# ============================================
# Export Limits
# ============================================

MAX_EXPORT_ROWS = 10000
EXPORT_CHUNK_SIZE = 1000

# ============================================
# Scraping Constants
# ============================================

SCRAPING_TIMEOUT = 30
SCRAPING_MAX_RETRIES = 3
SCRAPING_RETRY_DELAY = 2  # seconds

# Supported sources
SUPPORTED_SOURCES = ["linkedin", "twitter", "crunchbase", "company_website"]

# User agents for rotation
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0",
]

# ============================================
# Email Templates
# ============================================

EMAIL_TEMPLATES = {
    "lead_export_ready": {
        "subject": "Your Lead Export is Ready",
        "template_id": "d-1234567890"
    },
    "campaign_completed": {
        "subject": "Campaign Completed: {campaign_name}",
        "template_id": "d-0987654321"
    },
    "campaign_failed": {
        "subject": "Campaign Failed: {campaign_name}",
        "template_id": "d-1122334455"
    },
    "daily_analytics": {
        "subject": "Daily Lead Generation Report",
        "template_id": "d-5566778899"
    }
}

# ============================================
# Webhook Events
# ============================================

WEBHOOK_EVENTS = [
    "campaign.started",
    "campaign.completed",
    "campaign.failed",
    "lead.created",
    "lead.qualified",
    "lead.converted",
    "scraping.job.started",
    "scraping.job.completed",
]

# ============================================
# Error Codes
# ============================================

ERROR_CODES = {
    "VALIDATION_ERROR": "ERR_001",
    "RATE_LIMIT_EXCEEDED": "ERR_002",
    "UNAUTHORIZED": "ERR_003",
    "FORBIDDEN": "ERR_004",
    "NOT_FOUND": "ERR_005",
    "CONFLICT": "ERR_006",
    "INTERNAL_ERROR": "ERR_007",
    "SERVICE_UNAVAILABLE": "ERR_008",
    "QUOTA_EXCEEDED": "ERR_009",
    "INVALID_API_KEY": "ERR_010",
}

# ============================================
# Log Levels
# ============================================

LOG_LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# ============================================
# File Upload
# ============================================

ALLOWED_EXPORT_FORMATS = ["csv", "json", "excel"]
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB

# ============================================
# Date Formats
# ============================================

DATE_FORMAT = "%Y-%m-%d"
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"