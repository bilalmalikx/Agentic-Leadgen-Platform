"""
Notification Service
Send notifications via email, Slack, and webhooks
"""

from typing import Dict, Any, Optional, List
from uuid import UUID
import json
import httpx
from datetime import datetime

from app.core.logging import get_logger
from app.core.config import settings
from app.services.email_service import EmailService

logger = get_logger(__name__)


class NotificationService:
    """Service for sending notifications across multiple channels"""
    
    def __init__(self):
        self.email_service = EmailService()
        self.http_client = httpx.AsyncClient(timeout=10.0)
    
    async def send_notification(
        self,
        user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        channels: List[str] = ["email"]
    ):
        """
        Send notification to user via specified channels
        """
        # Get user preferences from database
        user = await self._get_user(user_id)
        if not user:
            logger.error(f"User {user_id} not found for notification")
            return
        
        results = {}
        
        if "email" in channels and user.get("email_notifications", True):
            results["email"] = await self._send_email_notification(
                user_email=user["email"],
                title=title,
                message=message,
                data=data
            )
        
        if "slack" in channels and user.get("slack_webhook_url"):
            results["slack"] = await self._send_slack_notification(
                webhook_url=user["slack_webhook_url"],
                title=title,
                message=message,
                data=data
            )
        
        logger.info(f"Notification sent to user {user_id}: {results}")
        return results
    
    async def _send_email_notification(
        self,
        user_email: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send email notification"""
        try:
            # Use template or plain email
            if data and data.get("template_name"):
                result = await self.email_service.send_template_email(
                    to_email=user_email,
                    template_name=data["template_name"],
                    template_data=data.get("template_data", {})
                )
            else:
                result = await self.email_service.send_email(
                    to_email=user_email,
                    subject=title,
                    content=message
                )
            
            return {"success": result.get("success", False), "channel": "email"}
            
        except Exception as e:
            logger.error(f"Failed to send email notification: {e}")
            return {"success": False, "error": str(e), "channel": "email"}
    
    async def _send_slack_notification(
        self,
        webhook_url: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Send Slack notification"""
        try:
            slack_payload = {
                "blocks": [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": title
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": message
                        }
                    }
                ]
            }
            
            # Add fields if data provided
            if data:
                fields = []
                for key, value in data.items():
                    if isinstance(value, (dict, list)):
                        value = json.dumps(value)[:200]
                    fields.append({
                        "type": "mrkdwn",
                        "text": f"*{key}:* {str(value)[:100]}"
                    })
                
                if fields:
                    slack_payload["blocks"].append({
                        "type": "section",
                        "fields": fields[:10]  # Slack limit 10 fields
                    })
            
            # Add timestamp
            slack_payload["blocks"].append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🕐 {datetime.utcnow().isoformat()}"
                    }
                ]
            })
            
            response = await self.http_client.post(webhook_url, json=slack_payload)
            
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "channel": "slack"
            }
            
        except Exception as e:
            logger.error(f"Failed to send Slack notification: {e}")
            return {"success": False, "error": str(e), "channel": "slack"}
    
    async def notify_campaign_started(
        self,
        campaign_id: UUID,
        campaign_name: str,
        user_id: UUID
    ):
        """Notify that a campaign has started"""
        await self.send_notification(
            user_id=user_id,
            notification_type="campaign_started",
            title=f"Campaign Started: {campaign_name}",
            message=f"Your campaign '{campaign_name}' has started generating leads.",
            data={
                "campaign_id": str(campaign_id),
                "campaign_name": campaign_name,
                "started_at": datetime.utcnow().isoformat()
            },
            channels=["email", "slack"]
        )
    
    async def notify_campaign_completed(
        self,
        campaign_id: UUID,
        campaign_name: str,
        total_leads: int,
        user_id: UUID,
        download_url: Optional[str] = None
    ):
        """Notify that a campaign has completed"""
        await self.send_notification(
            user_id=user_id,
            notification_type="campaign_completed",
            title=f"Campaign Completed: {campaign_name}",
            message=f"Your campaign '{campaign_name}' has completed. Generated {total_leads} leads.",
            data={
                "campaign_id": str(campaign_id),
                "campaign_name": campaign_name,
                "total_leads": total_leads,
                "download_url": download_url,
                "completed_at": datetime.utcnow().isoformat()
            },
            channels=["email", "slack"]
        )
    
    async def notify_campaign_failed(
        self,
        campaign_id: UUID,
        campaign_name: str,
        error_message: str,
        user_id: UUID
    ):
        """Notify that a campaign has failed"""
        await self.send_notification(
            user_id=user_id,
            notification_type="campaign_failed",
            title=f"Campaign Failed: {campaign_name}",
            message=f"Your campaign '{campaign_name}' failed. Error: {error_message}",
            data={
                "campaign_id": str(campaign_id),
                "campaign_name": campaign_name,
                "error": error_message,
                "failed_at": datetime.utcnow().isoformat()
            },
            channels=["email", "slack"]
        )
    
    async def notify_lead_qualified(
        self,
        lead_id: UUID,
        lead_email: str,
        score: int,
        campaign_name: str,
        user_id: UUID
    ):
        """Notify that a lead has been qualified"""
        await self.send_notification(
            user_id=user_id,
            notification_type="lead_qualified",
            title=f"New Qualified Lead: {lead_email}",
            message=f"A new lead has been qualified with score {score} from campaign '{campaign_name}'.",
            data={
                "lead_id": str(lead_id),
                "lead_email": lead_email,
                "score": score,
                "campaign_name": campaign_name
            },
            channels=["slack"]  # Only Slack for high-volume notifications
        )
    
    async def send_daily_analytics(
        self,
        user_id: UUID,
        user_email: str,
        stats: Dict[str, Any]
    ):
        """Send daily analytics report via email"""
        template_data = {
            "date": datetime.utcnow().strftime("%Y-%m-%d"),
            "total_leads": stats.get("total_leads", 0),
            "new_leads": stats.get("new_leads", 0),
            "qualified_leads": stats.get("qualified_leads", 0),
            "converted_leads": stats.get("converted_leads", 0),
            "active_campaigns": stats.get("active_campaigns", 0),
            "average_score": stats.get("average_score", 0),
            "top_sources": stats.get("top_sources", []),
            "dashboard_url": f"{settings.app_host}/dashboard"
        }
        
        await self.email_service.send_template_email(
            to_email=user_email,
            template_name="daily_analytics",
            template_data=template_data
        )
    
    async def _get_user(self, user_id: UUID) -> Optional[Dict[str, Any]]:
        """Get user from database"""
        try:
            from app.db.session import get_sync_session
            from app.models.user import User
            
            with get_sync_session() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return {
                        "id": str(user.id),
                        "email": user.email,
                        "email_notifications": user.email_notifications,
                        "slack_webhook_url": user.slack_webhook_url
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()