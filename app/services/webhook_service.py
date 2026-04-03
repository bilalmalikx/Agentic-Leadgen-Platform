"""
Webhook Service
Deliver webhook events to subscribed endpoints with retry logic
"""

from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
import json
import hmac
import hashlib
import httpx

from app.core.logging import get_logger
from app.core.config import settings
from app.models.webhook_delivery import WebhookDelivery, WebhookStatus

logger = get_logger(__name__)


class WebhookService:
    """Service for delivering webhook events"""
    
    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=settings.webhook_timeout_seconds)
    
    async def deliver_webhook(
        self,
        url: str,
        event_type: str,
        payload: Dict[str, Any],
        webhook_id: Optional[str] = None,
        secret: Optional[str] = None,
        campaign_id: Optional[UUID] = None,
        lead_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Deliver webhook to endpoint
        Returns delivery result
        """
        
        # Create webhook payload
        webhook_payload = {
            "id": f"evt_{datetime.utcnow().timestamp()}",
            "event": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": payload
        }
        
        # Create delivery record
        delivery = await self._create_delivery_record(
            url=url,
            event_type=event_type,
            webhook_id=webhook_id,
            campaign_id=campaign_id,
            lead_id=lead_id,
            payload=webhook_payload
        )
        
        try:
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "User-Agent": "LeadGen-Webhook/1.0",
                "X-Webhook-Event": event_type,
                "X-Webhook-Delivery-ID": str(delivery.id)
            }
            
            # Add signature if secret provided
            if secret:
                signature = self._generate_signature(secret, json.dumps(webhook_payload))
                headers["X-Webhook-Signature"] = signature
            
            # Send webhook
            response = await self.http_client.post(
                url,
                json=webhook_payload,
                headers=headers
            )
            
            # Update delivery record
            await self._update_delivery_record(
                delivery_id=delivery.id,
                status=WebhookStatus.SUCCESS if response.status_code < 400 else WebhookStatus.FAILED,
                status_code=response.status_code,
                response_body=response.text[:1000],
                response_headers=dict(response.headers)
            )
            
            logger.info(f"Webhook delivered to {url}, status: {response.status_code}")
            
            return {
                "success": response.status_code < 400,
                "status_code": response.status_code,
                "delivery_id": str(delivery.id)
            }
            
        except Exception as e:
            logger.error(f"Webhook delivery failed to {url}: {e}")
            
            # Update delivery record as failed
            await self._update_delivery_record(
                delivery_id=delivery.id,
                status=WebhookStatus.FAILED,
                error_message=str(e)
            )
            
            # Schedule retry if needed
            if delivery.retry_count < delivery.max_retries:
                await self._schedule_retry(delivery.id)
            
            return {
                "success": False,
                "error": str(e),
                "delivery_id": str(delivery.id)
            }
    
    async def deliver_batch(
        self,
        webhooks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Deliver multiple webhooks in parallel
        """
        import asyncio
        
        tasks = []
        for webhook in webhooks:
            task = self.deliver_webhook(
                url=webhook["url"],
                event_type=webhook["event_type"],
                payload=webhook["payload"],
                webhook_id=webhook.get("webhook_id"),
                secret=webhook.get("secret"),
                campaign_id=webhook.get("campaign_id"),
                lead_id=webhook.get("lead_id")
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [
            {"success": False, "error": str(r)} if isinstance(r, Exception) else r
            for r in results
        ]
    
    async def retry_failed_delivery(self, delivery_id: UUID) -> Dict[str, Any]:
        """
        Retry a failed webhook delivery
        """
        from app.db.session import get_sync_session
        from app.models.webhook_delivery import WebhookDelivery
        
        with get_sync_session() as db:
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
            
            if not delivery:
                return {"success": False, "error": "Delivery not found"}
            
            if delivery.status not in [WebhookStatus.FAILED, WebhookStatus.RETRYING]:
                return {"success": False, "error": f"Cannot retry delivery with status {delivery.status}"}
            
            # Retry delivery
            result = await self.deliver_webhook(
                url=delivery.webhook_url,
                event_type=delivery.event_type,
                payload=delivery.event_data,
                webhook_id=delivery.webhook_id,
                campaign_id=delivery.campaign_id,
                lead_id=delivery.lead_id
            )
            
            return result
    
    async def _create_delivery_record(
        self,
        url: str,
        event_type: str,
        payload: Dict[str, Any],
        webhook_id: Optional[str] = None,
        campaign_id: Optional[UUID] = None,
        lead_id: Optional[UUID] = None
    ) -> WebhookDelivery:
        """Create webhook delivery record in database"""
        from app.db.session import get_sync_session
        from app.models.webhook_delivery import WebhookDelivery
        
        with get_sync_session() as db:
            delivery = WebhookDelivery(
                webhook_url=url,
                webhook_id=webhook_id,
                event_type=event_type,
                event_data=payload,
                campaign_id=campaign_id,
                lead_id=lead_id,
                status=WebhookStatus.DELIVERING,
                request_body=json.dumps(payload)[:10000],
                request_headers={}
            )
            db.add(delivery)
            db.commit()
            db.refresh(delivery)
            
            return delivery
    
    async def _update_delivery_record(
        self,
        delivery_id: UUID,
        status: WebhookStatus,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
        response_headers: Optional[Dict] = None,
        error_message: Optional[str] = None
    ):
        """Update webhook delivery record"""
        from app.db.session import get_sync_session
        from app.models.webhook_delivery import WebhookDelivery
        
        with get_sync_session() as db:
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
            
            if delivery:
                delivery.status = status
                delivery.delivered_at = datetime.utcnow()
                
                if status_code is not None:
                    delivery.response_status_code = status_code
                if response_body is not None:
                    delivery.response_body = response_body
                if response_headers is not None:
                    delivery.response_headers = response_headers
                if error_message is not None:
                    delivery.status_message = error_message
                
                db.commit()
    
    async def _schedule_retry(self, delivery_id: UUID):
        """Schedule retry for failed delivery"""
        from app.db.session import get_sync_session
        from app.models.webhook_delivery import WebhookDelivery
        from app.workers.webhook_tasks import retry_webhook_delivery_task
        
        with get_sync_session() as db:
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == delivery_id).first()
            
            if delivery:
                delivery.schedule_retry()
                db.commit()
                
                # Schedule Celery task for retry
                retry_webhook_delivery_task.apply_async(
                    args=[str(delivery_id)],
                    countdown=delivery.next_retry_at - datetime.utcnow()
                )
    
    def _generate_signature(self, secret: str, payload: str) -> str:
        """Generate HMAC signature for webhook payload"""
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    async def close(self):
        """Close HTTP client"""
        await self.http_client.aclose()