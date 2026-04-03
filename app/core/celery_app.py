"""
Celery Configuration for Background Tasks
Supports task routing, retries, and monitoring
"""

from celery import Celery
from celery.schedules import crontab
from kombu import Queue, Exchange
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# Create Celery app instance
celery_app = Celery(
    "lead_generation_system",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.lead_tasks",
        "app.workers.scraping_tasks",
        "app.workers.enrichment_tasks",
        "app.workers.email_tasks",
        "app.workers.webhook_tasks",
        "app.workers.cleanup_tasks",
    ]
)

# Configure Celery
celery_app.conf.update(
    # Task settings
    task_track_started=settings.celery_task_track_started,
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    
    # Worker settings
    worker_concurrency=settings.celery_worker_concurrency,
    worker_prefetch_multiplier=1,  # Fair distribution
    worker_max_tasks_per_child=settings.celery_worker_max_tasks_per_child,
    
    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },
    
    # Retry settings
    task_default_retry_delay=30,
    task_max_retries=3,
    
    # Task routing
    task_queues=(
        Queue("high_priority", Exchange("high_priority"), routing_key="high_priority"),
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("low_priority", Exchange("low_priority"), routing_key="low_priority"),
        Queue("scraping", Exchange("scraping"), routing_key="scraping"),
        Queue("email", Exchange("email"), routing_key="email"),
    ),
    
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    
    task_routes={
        "app.workers.lead_tasks.generate_leads_task": {"queue": "high_priority"},
        "app.workers.scraping_tasks.*": {"queue": "scraping"},
        "app.workers.email_tasks.*": {"queue": "email"},
        "app.workers.cleanup_tasks.*": {"queue": "low_priority"},
    },
    
    # Periodic tasks (Celery Beat)
    beat_schedule={
        "cleanup-old-leads": {
            "task": "app.workers.cleanup_tasks.cleanup_old_leads",
            "schedule": crontab(hour=2, minute=0),  # Run at 2 AM daily
            "options": {"queue": "low_priority"}
        },
        "send-daily-analytics": {
            "task": "app.workers.cleanup_tasks.send_daily_analytics",
            "schedule": crontab(hour=9, minute=0),  # Run at 9 AM daily
            "options": {"queue": "low_priority"}
        },
        "refresh-embeddings": {
            "task": "app.workers.enrichment_tasks.refresh_lead_embeddings",
            "schedule": crontab(hour=3, minute=0),  # Run at 3 AM daily
            "options": {"queue": "low_priority"}
        },
        "health-check": {
            "task": "app.workers.cleanup_tasks.health_check_task",
            "schedule": crontab(minute="*/5"),  # Run every 5 minutes
            "options": {"queue": "low_priority"}
        }
    },
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
)

# Task execution callbacks
@celery_app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery"""
    logger.info(f"Request: {self.request!r}")


# Error handling for failed tasks
def on_failure(self, exc, task_id, args, kwargs, einfo):
    """Handle task failure"""
    logger.error(f"Task {task_id} failed: {exc}")
    # Send alert to monitoring system
    # Could send to Slack, Sentry, etc.


# Attach error handler
celery_app.conf.task_failure_handler = on_failure


# Flower monitoring configuration (if enabled)
if settings.prometheus_enabled:
    celery_app.conf.worker_send_task_events = True
    celery_app.conf.task_send_sent_event = True