"""
Celery Tasks for Email Sending
Background jobs for bulk email delivery
"""

from celery import Task
from typing import List, Dict, Any, Optional
from uuid import UUID

from app.core.celery_app import celery_app
from app.core.database import get_sync_session
from app.core.logging import get_logger
from app.core.config import settings

logger = get_logger(__name__)


class EmailTask(Task):
    """Base email task with rate limiting"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 5}
    retry_backoff = True
    retry_backoff_max = 300


@celery_app.task(base=EmailTask, bind=True, name="send_single_email_task")
def send_single_email_task(
    self,
    to_email: str,
    subject: str,
    content: str,
    lead_id: Optional[str] = None,
    campaign_id: Optional[str] = None
):
    """
    Send a single email
    """
    logger.info(f"Sending email to {to_email}")
    
    try:
        from app.services.email_service import EmailService
        
        email_service = EmailService()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            email_service.send_email(
                to_email=to_email,
                subject=subject,
                content=content,
                lead_id=UUID(lead_id) if lead_id else None,
                campaign_id=UUID(campaign_id) if campaign_id else None
            )
        )
        loop.close()
        
        logger.info(f"Email sent to {to_email}: {result}")
        return {"to_email": to_email, "success": result.get("success", False)}
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        self.retry(exc=e)
        return {"to_email": to_email, "error": str(e)}


@celery_app.task(base=EmailTask, bind=True, name="send_bulk_emails_task")
def send_bulk_emails_task(
    self,
    recipients: List[Dict[str, Any]],
    subject: str,
    content: str,
    template_id: Optional[str] = None
):
    """
    Send bulk emails with rate limiting
    """
    logger.info(f"Sending bulk emails to {len(recipients)} recipients")
    
    try:
        from app.services.email_service import EmailService
        
        email_service = EmailService()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            email_service.send_bulk_emails(
                recipients=recipients,
                subject=subject,
                content=content,
                template_id=template_id
            )
        )
        loop.close()
        
        logger.info(f"Bulk email completed: {result.get('successful')} sent, {result.get('failed')} failed")
        return result
        
    except Exception as e:
        logger.error(f"Bulk email failed: {e}")
        self.retry(exc=e)
        return {"error": str(e)}


@celery_app.task(base=EmailTask, bind=True, name="send_campaign_completion_email")
def send_campaign_completion_email(self, campaign_id: str, user_email: str, campaign_name: str, total_leads: int):
    """
    Send campaign completion notification email
    """
    logger.info(f"Sending campaign completion email for {campaign_id} to {user_email}")
    
    try:
        from app.services.email_service import EmailService
        from app.core.constants import EMAIL_TEMPLATES
        
        email_service = EmailService()
        
        template_data = {
            "campaign_name": campaign_name,
            "campaign_id": campaign_id,
            "total_leads": total_leads,
            "dashboard_url": f"{settings.app_host}/dashboard/campaigns/{campaign_id}"
        }
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            email_service.send_template_email(
                to_email=user_email,
                template_name="campaign_completed",
                template_data=template_data
            )
        )
        loop.close()
        
        return {"campaign_id": campaign_id, "success": result.get("success", False)}
        
    except Exception as e:
        logger.error(f"Failed to send campaign completion email: {e}")
        return {"campaign_id": campaign_id, "error": str(e)}


@celery_app.task(base=EmailTask, bind=True, name="send_daily_analytics_email")
def send_daily_analytics_email(self, user_id: str, user_email: str, stats: Dict[str, Any]):
    """
    Send daily analytics report email
    """
    logger.info(f"Sending daily analytics to {user_email}")
    
    try:
        from app.services.email_service import EmailService
        
        email_service = EmailService()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            email_service.send_daily_analytics(
                user_id=UUID(user_id),
                user_email=user_email,
                stats=stats
            )
        )
        loop.close()
        
        return {"user_email": user_email, "success": result.get("success", False)}
        
    except Exception as e:
        logger.error(f"Failed to send daily analytics: {e}")
        return {"user_email": user_email, "error": str(e)}