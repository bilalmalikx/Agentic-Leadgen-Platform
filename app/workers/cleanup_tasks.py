"""
Celery Tasks for Cleanup and Maintenance
Periodic jobs for data cleanup, backup, and maintenance
"""

from celery import Task
from typing import Dict, Any
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.core.database import get_sync_session
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class CleanupTask(Task):
    """Base cleanup task"""
    
    ignore_result = True


@celery_app.task(base=CleanupTask, bind=True, name="cleanup_old_leads_task")
def cleanup_old_leads_task(self, days: int = 90):
    """
    Soft delete leads older than specified days
    """
    logger.info(f"Cleaning up leads older than {days} days")
    
    try:
        from app.models.lead import Lead
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with get_sync_session() as db:
            # Get old leads
            old_leads = db.query(Lead).filter(
                Lead.created_at < cutoff_date,
                Lead.is_deleted == False
            ).all()
            
            # Soft delete
            for lead in old_leads:
                lead.is_deleted = True
                lead.deleted_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Cleaned up {len(old_leads)} old leads")
            return {"deleted_count": len(old_leads), "days": days}
            
    except Exception as e:
        logger.error(f"Cleanup old leads failed: {e}")
        return {"error": str(e)}


@celery_app.task(base=CleanupTask, bind=True, name="cleanup_failed_scraping_jobs")
def cleanup_failed_scraping_jobs(self, days: int = 7):
    """
    Clean up old failed scraping jobs
    """
    logger.info(f"Cleaning up failed scraping jobs older than {days} days")
    
    try:
        from app.models.scraping_job import ScrapingJob, JobStatus
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        with get_sync_session() as db:
            old_jobs = db.query(ScrapingJob).filter(
                ScrapingJob.status == JobStatus.FAILED,
                ScrapingJob.created_at < cutoff_date
            ).all()
            
            for job in old_jobs:
                db.delete(job)
            
            db.commit()
            
            logger.info(f"Cleaned up {len(old_jobs)} failed scraping jobs")
            return {"deleted_count": len(old_jobs)}
            
    except Exception as e:
        logger.error(f"Cleanup failed jobs failed: {e}")
        return {"error": str(e)}


@celery_app.task(base=CleanupTask, bind=True, name="cleanup_old_exports")
def cleanup_old_exports(self, hours: int = 24):
    """
    Clean up old export files
    """
    logger.info(f"Cleaning up export files older than {hours} hours")
    
    try:
        from app.services.export_service import ExportService
        
        export_service = ExportService()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        deleted = loop.run_until_complete(export_service.cleanup_old_exports(hours))
        loop.close()
        
        logger.info(f"Cleaned up {deleted} old export files")
        return {"deleted_count": deleted}
        
    except Exception as e:
        logger.error(f"Cleanup exports failed: {e}")
        return {"error": str(e)}


@celery_app.task(base=CleanupTask, bind=True, name="reset_user_quotas")
def reset_user_quotas(self):
    """
    Reset monthly quotas for all users
    """
    logger.info("Resetting user quotas for new month")
    
    try:
        from app.models.user import User
        
        with get_sync_session() as db:
            users = db.query(User).all()
            
            for user in users:
                user.leads_generated_this_month = 0
                user.api_calls_this_month = 0
                user.quota_reset_at = datetime.utcnow()
            
            db.commit()
            
            logger.info(f"Reset quotas for {len(users)} users")
            return {"users_reset": len(users)}
            
    except Exception as e:
        logger.error(f"Reset quotas failed: {e}")
        return {"error": str(e)}


@celery_app.task(base=CleanupTask, bind=True, name="health_check_task")
def health_check_task(self):
    """
    Periodic health check of all services
    """
    logger.info("Running health check")
    
    try:
        from app.core.database import get_db_health
        from app.core.redis_client import get_redis_health
        from app.vector_store.vector_client import get_chroma_health
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        db_health = loop.run_until_complete(get_db_health())
        redis_health = loop.run_until_complete(get_redis_health())
        chroma_health = loop.run_until_complete(get_chroma_health())
        
        loop.close()
        
        status = {
            "database": db_health.get("status"),
            "redis": redis_health.get("status"),
            "chromadb": chroma_health.get("status"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Alert if any service is unhealthy
        unhealthy = [k for k, v in status.items() if v != "healthy" and k != "timestamp"]
        if unhealthy:
            logger.warning(f"Unhealthy services detected: {unhealthy}")
        
        return status
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"error": str(e)}


@celery_app.task(base=CleanupTask, bind=True, name="send_daily_analytics")
def send_daily_analytics(self):
    """
    Send daily analytics reports to all users
    """
    logger.info("Sending daily analytics reports")
    
    try:
        from app.models.user import User
        from app.services.analytics_service import AnalyticsService
        from app.workers.email_tasks import send_daily_analytics_email
        
        with get_sync_session() as db:
            users = db.query(User).filter(User.email_notifications == True).all()
            
            sent_count = 0
            for user in users:
                # Get user analytics
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                analytics_service = AnalyticsService(db)
                stats = loop.run_until_complete(
                    analytics_service.get_dashboard_summary(user.id)
                )
                loop.close()
                
                # Send email
                send_daily_analytics_email.delay(
                    user_id=str(user.id),
                    user_email=user.email,
                    stats=stats
                )
                sent_count += 1
            
            logger.info(f"Sent daily analytics to {sent_count} users")
            return {"sent_count": sent_count}
            
    except Exception as e:
        logger.error(f"Send daily analytics failed: {e}")
        return {"error": str(e)}


@celery_app.task(base=CleanupTask, bind=True, name="backup_database_task")
def backup_database_task(self):
    """
    Backup database (if configured)
    """
    logger.info("Starting database backup")
    
    try:
        import subprocess
        import os
        
        backup_dir = "/backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = f"{backup_dir}/leadgen_backup_{timestamp}.sql"
        
        # Run pg_dump
        result = subprocess.run(
            [
                "pg_dump",
                "-h", settings.database_url.split("@")[1].split("/")[0].split(":")[0],
                "-p", "5432",
                "-U", "leadgen",
                "-d", "leadgen",
                "-f", backup_file
            ],
            capture_output=True
        )
        
        if result.returncode == 0:
            logger.info(f"Database backup completed: {backup_file}")
            return {"backup_file": backup_file, "size_bytes": os.path.getsize(backup_file)}
        else:
            logger.error(f"Database backup failed: {result.stderr}")
            return {"error": result.stderr}
            
    except Exception as e:
        logger.error(f"Backup task failed: {e}")
        return {"error": str(e)}