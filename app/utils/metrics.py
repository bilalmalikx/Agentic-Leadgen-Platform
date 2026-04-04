"""
Metrics
Prometheus metrics collection for monitoring
"""

from typing import Dict, Any, Optional
from prometheus_client import Counter, Histogram, Gauge, Info, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response
import time
from functools import wraps

from app.core.logging import get_logger

logger = get_logger(__name__)


# ============================================
# Define Metrics
# ============================================

# API Metrics
api_requests_total = Counter(
    'api_requests_total',
    'Total number of API requests',
    ['method', 'endpoint', 'status']
)

api_request_duration = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10]
)

# Lead Metrics
leads_generated_total = Counter(
    'leads_generated_total',
    'Total number of leads generated',
    ['source', 'campaign_id']
)

leads_qualified_total = Counter(
    'leads_qualified_total',
    'Total number of leads qualified',
    ['quality']
)

leads_score_gauge = Gauge(
    'leads_score',
    'Current lead scores',
    ['lead_id']
)

# Campaign Metrics
campaigns_active = Gauge(
    'campaigns_active',
    'Number of active campaigns'
)

campaigns_completed_total = Counter(
    'campaigns_completed_total',
    'Total number of campaigns completed'
)

# Scraping Metrics
scraping_requests_total = Counter(
    'scraping_requests_total',
    'Total number of scraping requests',
    ['source', 'status']
)

scraping_duration = Histogram(
    'scraping_duration_seconds',
    'Scraping duration in seconds',
    ['source'],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

# Queue Metrics
queue_size = Gauge(
    'queue_size',
    'Size of Celery queues',
    ['queue_name']
)

# Database Metrics
db_connections = Gauge(
    'db_connections',
    'Number of active database connections'
)

db_query_duration = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1]
)

# LLM Metrics
llm_requests_total = Counter(
    'llm_requests_total',
    'Total number of LLM requests',
    ['provider', 'status']
)

llm_request_duration = Histogram(
    'llm_request_duration_seconds',
    'LLM request duration in seconds',
    ['provider'],
    buckets=[0.1, 0.5, 1, 2, 5, 10, 30]
)

# Cache Metrics
cache_hits_total = Counter(
    'cache_hits_total',
    'Total number of cache hits'
)

cache_misses_total = Counter(
    'cache_misses_total',
    'Total number of cache misses'
)


# ============================================
# Metric Recording Functions
# ============================================

def record_api_request(method: str, endpoint: str, status_code: int, duration: float):
    """Record API request metrics"""
    api_requests_total.labels(method=method, endpoint=endpoint, status=str(status_code)).inc()
    api_request_duration.labels(method=method, endpoint=endpoint).observe(duration)


def record_lead_generated(source: str, campaign_id: str):
    """Record lead generation metric"""
    leads_generated_total.labels(source=source, campaign_id=campaign_id).inc()


def record_lead_qualified(quality: str):
    """Record lead qualification metric"""
    leads_qualified_total.labels(quality=quality).inc()


def record_lead_score(lead_id: str, score: int):
    """Record lead score metric"""
    leads_score_gauge.labels(lead_id=lead_id).set(score)


def record_scraping_request(source: str, success: bool):
    """Record scraping request metric"""
    status = "success" if success else "failed"
    scraping_requests_total.labels(source=source, status=status).inc()


def record_scraping_duration(source: str, duration: float):
    """Record scraping duration metric"""
    scraping_duration.labels(source=source).observe(duration)


def record_queue_size(queue_name: str, size: int):
    """Record queue size metric"""
    queue_size.labels(queue_name=queue_name).set(size)


def record_db_connection_count(count: int):
    """Record database connection count"""
    db_connections.set(count)


def record_db_query_duration(operation: str, duration: float):
    """Record database query duration"""
    db_query_duration.labels(operation=operation).observe(duration)


def record_llm_request(provider: str, success: bool, duration: float):
    """Record LLM request metric"""
    status = "success" if success else "failed"
    llm_requests_total.labels(provider=provider, status=status).inc()
    llm_request_duration.labels(provider=provider).observe(duration)


def record_cache_hit():
    """Record cache hit"""
    cache_hits_total.inc()


def record_cache_miss():
    """Record cache miss"""
    cache_misses_total.inc()


def update_campaigns_active(count: int):
    """Update active campaigns count"""
    campaigns_active.set(count)


def record_campaign_completed():
    """Record campaign completion"""
    campaigns_completed_total.inc()


# ============================================
# Decorators
# ============================================

def time_request(endpoint: str):
    """Decorator to time API requests"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Get status code from response
                status_code = getattr(result, 'status_code', 200)
                record_api_request("GET", endpoint, status_code, duration)
                
                return result
            except Exception as e:
                duration = time.time() - start_time
                record_api_request("GET", endpoint, 500, duration)
                raise
        return wrapper
    return decorator


def time_db_query(operation: str):
    """Decorator to time database queries"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                record_db_query_duration(operation, duration)
                return result
            except Exception as e:
                duration = time.time() - start_time
                record_db_query_duration(operation, duration)
                raise
        return wrapper
    return decorator


# ============================================
# FastAPI Endpoint
# ============================================

async def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint"""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


def setup_metrics(app):
    """Setup metrics endpoint in FastAPI app"""
    app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], include_in_schema=False)
    logger.info("Prometheus metrics endpoint configured at /metrics")