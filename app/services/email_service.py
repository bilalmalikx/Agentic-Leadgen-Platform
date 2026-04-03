"""
Email Service
SendGrid integration for sending emails with templates and tracking
"""

from typing import List, Dict, Any, Optional
from uuid import UUID
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, TemplateId
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.logging import get_logger
from app.core.config import settings
from app.models.email_log import EmailLog, EmailStatus, EmailType

logger = get_logger(__name__)


class EmailService:
    """Service for sending emails via SendGrid"""
    
    def __init__(self):
        self.client = SendGridAPIClient(settings.sendgrid_api_key) if settings.sendgrid_api_key else None
        self.from_email = settings.sendgrid_from_email
        self.executor = ThreadPoolExecutor(max_workers=5)
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        content: str,
        html_content: Optional[str] = None,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
        lead_id: Optional[UUID] = None,
        campaign_id: Optional[UUID] = None,
        email_type: EmailType = EmailType.OUTREACH
    ) -> Dict[str, Any]:
        """
        Send a single email
        """
        if not self.client:
            logger.warning("SendGrid not configured, skipping email send")
            return {"success": False, "error": "SendGrid not configured"}
        
        try:
            # Create email message
            message = Mail(
                from_email=self.from_email,
                to_emails=to_email,
                subject=subject
            )
            
            if template_id and template_data:
                # Use template
                message.template_id = template_id
                message.dynamic_template_data = template_data
            else:
                # Use plain content
                if html_content:
                    message.content = Content("text/html", html_content)
                else:
                    message.content = Content("text/plain", content)
            
            # Send in thread pool (SendGrid client is sync)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                self.executor,
                lambda: self.client.send(message)
            )
            
            # Log email
            await self._log_email(
                to_email=to_email,
                subject=subject,
                content=content,
                html_content=html_content,
                template_id=template_id,
                template_data=template_data,
                lead_id=lead_id,
                campaign_id=campaign_id,
                email_type=email_type,
                provider_message_id=response.headers.get('X-Message-Id'),
                status=EmailStatus.SENT if response.status_code < 400 else EmailStatus.FAILED
            )
            
            logger.info(f"Email sent to {to_email}, status: {response.status_code}")
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "message_id": response.headers.get('X-Message-Id')
            }
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            
            await self._log_email(
                to_email=to_email,
                subject=subject,
                content=content,
                html_content=html_content,
                lead_id=lead_id,
                campaign_id=campaign_id,
                email_type=email_type,
                status=EmailStatus.FAILED,
                error_message=str(e)
            )
            
            return {"success": False, "error": str(e)}
    
    async def send_bulk_emails(
        self,
        recipients: List[Dict[str, Any]],
        subject: str,
        content: str,
        template_id: Optional[str] = None,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Send bulk emails with rate limiting
        """
        successful = 0
        failed = 0
        errors = []
        
        for i in range(0, len(recipients), batch_size):
            batch = recipients[i:i + batch_size]
            
            # Process batch in parallel
            tasks = []
            for recipient in batch:
                task = self.send_email(
                    to_email=recipient["email"],
                    subject=subject,
                    content=content,
                    template_id=template_id,
                    template_data=recipient.get("template_data"),
                    lead_id=recipient.get("lead_id"),
                    campaign_id=recipient.get("campaign_id")
                )
                tasks.append(task)
            
            results = await asyncio.gather(*tasks)
            
            for result in results:
                if result.get("success"):
                    successful += 1
                else:
                    failed += 1
                    errors.append(result.get("error"))
            
            # Rate limiting: wait between batches
            if i + batch_size < len(recipients):
                await asyncio.sleep(1 / settings.email_rate_limit_per_second)
        
        return {
            "total": len(recipients),
            "successful": successful,
            "failed": failed,
            "errors": errors[:50]  # Limit errors
        }
    
    async def send_template_email(
        self,
        to_email: str,
        template_name: str,
        template_data: Dict[str, Any],
        lead_id: Optional[UUID] = None,
        campaign_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Send email using a template
        """
        from app.core.constants import EMAIL_TEMPLATES
        
        template_config = EMAIL_TEMPLATES.get(template_name)
        if not template_config:
            raise ValueError(f"Template {template_name} not found")
        
        return await self.send_email(
            to_email=to_email,
            subject=template_config["subject"].format(**template_data),
            content="",
            template_id=template_config["template_id"],
            template_data=template_data,
            lead_id=lead_id,
            campaign_id=campaign_id,
            email_type=EmailType.NOTIFICATION
        )
    
    async def send_campaign_completed_notification(
        self,
        to_email: str,
        campaign_name: str,
        campaign_id: UUID,
        total_leads: int,
        download_url: Optional[str] = None
    ):
        """Send campaign completed notification"""
        template_data = {
            "campaign_name": campaign_name,
            "campaign_id": str(campaign_id),
            "total_leads": total_leads,
            "download_url": download_url or "",
            "dashboard_url": f"{settings.app_host}/dashboard/campaigns/{campaign_id}"
        }
        
        return await self.send_template_email(
            to_email=to_email,
            template_name="campaign_completed",
            template_data=template_data
        )
    
    async def send_lead_export_ready(
        self,
        to_email: str,
        export_format: str,
        download_url: str,
        lead_count: int
    ):
        """Send lead export ready notification"""
        template_data = {
            "export_format": export_format.upper(),
            "download_url": download_url,
            "lead_count": lead_count,
            "expires_in_hours": 24
        }
        
        return await self.send_template_email(
            to_email=to_email,
            template_name="lead_export_ready",
            template_data=template_data
        )
    
    async def _log_email(
        self,
        to_email: str,
        subject: str,
        content: str,
        html_content: Optional[str] = None,
        template_id: Optional[str] = None,
        template_data: Optional[Dict[str, Any]] = None,
        lead_id: Optional[UUID] = None,
        campaign_id: Optional[UUID] = None,
        email_type: EmailType = EmailType.OUTREACH,
        provider_message_id: Optional[str] = None,
        status: EmailStatus = EmailStatus.SENT,
        error_message: Optional[str] = None
    ):
        """Log email to database"""
        from app.db.session import get_sync_session
        from app.models.email_log import EmailLog
        
        try:
            with get_sync_session() as db:
                email_log = EmailLog(
                    lead_id=lead_id,
                    campaign_id=campaign_id,
                    email_type=email_type,
                    from_email=self.from_email,
                    to_email=to_email,
                    subject=subject,
                    content=content[:10000] if content else None,
                    content_html=html_content[:10000] if html_content else None,
                    template_id=template_id,
                    template_variables=template_data or {},
                    status=status,
                    provider_message_id=provider_message_id,
                    error_message=error_message
                )
                db.add(email_log)
                db.commit()
        except Exception as e:
            logger.error(f"Failed to log email: {e}")