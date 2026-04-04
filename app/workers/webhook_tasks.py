"""
Celery Tasks for Webhook Delivery
Background jobs for webhook event delivery with retry
"""

from celery import Task
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta

from app.core.celery_app import celery_app
from app.core.database import get_sync_session
from app.core.logging import get_logger

logger = get_logger(__name__)


class WebhookTask(Task):
    """Base webhook task with retry"""
    
    autoretry_for = (Exception,)
    retry_kwargs = {'max_retries': 5}
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True


@celery_app.task(base=WebhookTask, bind=True, name="deliver_webhook_task")
def deliver_webhook_task(
    self,
    webhook_id: str,
    url: str,
    event_type: str,
    payload: Dict[str, Any],
    secret: Optional[str] = None,
    campaign_id: Optional[str] = None,
    lead_id: Optional[str] = None
):
    """
    Deliver webhook to endpoint
    """
    logger.info(f"Delivering webhook {webhook_id} to {url}, event: {event_type}")
    
    try:
        from app.services.webhook_service import WebhookService
        
        webhook_service = WebhookService()
        
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            webhook_service.deliver_webhook(
                url=url,
                event_type=event_type,
                payload=payload,
                webhook_id=webhook_id,
                secret=secret,
                campaign_id=UUID(campaign_id) if campaign_id else None,
                lead_id=UUID(lead_id) if lead_id else None
            )
        )
        loop.close()
        
        logger.info(f"Webhook {webhook_id} delivered: {result}")
        return result
        
    except Exception as e:
        logger.error(f"Webhook {webhook_id} delivery failed: {e}")
        self.retry(exc=e)
        return {"webhook_id": webhook_id, "error": str(e)}


@celery_app.task(base=WebhookTask, bind=True, name="retry_webhook_delivery_task")
def retry_webhook_delivery_task(self, delivery_id: str):
    """
    Retry failed webhook delivery
    """
    logger.info(f"Retrying webhook delivery {delivery_id}")
    
    try:
        from app.services.webhook_service import WebhookService
        from app.models.webhook_delivery import WebhookDelivery
        
        with get_sync_session() as db:
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.id == UUID(delivery_id)).first()
            
            if not delivery:
                return {"delivery_id": delivery_id, "error": "Delivery not found"}
            
            if not delivery.can_retry():
                logger.warning(f"Delivery {delivery_id} cannot be retried, max retries reached")
                return {"delivery_id": delivery_id, "error": "Max retries reached"}
            
            webhook_service = WebhookService()
            
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                webhook_service.deliver_webhook(
                    url=delivery.webhook_url,
                    event_type=delivery.event_type,
                    payload=delivery.event_data,
                    webhook_id=delivery.webhook_id,
                    campaign_id=delivery.campaign_id,
                    lead_id=delivery.lead_id
                )
            )
            loop.close()
            
            return result
            
    except Exception as e:
        logger.error(f"Webhook retry failed for {delivery_id}: {e}")
        return {"delivery_id": delivery_id, "error": str(e)}


@celery_app.task(base=WebhookTask, bind=True, name="broadcast_webhook_event")
def broadcast_webhook_event(
    self,
    event_type: str,
    payload: Dict[str, Any],
    campaign_id: Optional[str] = None,
    lead_id: Optional[str] = None
):
    """
    Broadcast event to all subscribed webhooks
    """
    logger.info(f"Broadcasting event {event_type} to all subscribers")
    
    try:
        from app.db.repositories.webhook_repository import WebhookRepository
        
        with get_sync_session() as db:
            repo = WebhookRepository(db)
            webhooks = repo.get_active_by_event(event_type)
            
            results = []
            for webhook in webhooks:
                task = deliver_webhook_task.delay(
                    webhook_id=str(webhook.id),
                    url=webhook.url,
                    event_type=event_type,
                    payload=payload,
                    secret=webhook.secret,
                    campaign_id=campaign_id,
                    lead_id=lead_id
                )
                results.append({
                    "webhook_id": str(webhook.id),
                    "task_id": task.id
                })
            
            logger.info(f"Broadcasted event {event_type} to {len(webhooks)} webhooks")
            return {
                "event_type": event_type,
                "subscribers": len(webhooks),
                "tasks": results
            }
            
    except Exception as e:
        logger.error(f"Webhook broadcast failed: {e}")
        return {"event_type": event_type, "error": str(e)}


@celery_app.task(base=WebhookTask, bind=True, name="schedule_webhook_retries")
def schedule_webhook_retries(self):
    """
    Schedule retries for failed webhook deliveries
    """
    logger.info("Scheduling webhook retries for failed deliveries")
    
    try:
        from app.models.webhook_delivery import WebhookDelivery, WebhookStatus
        
        with get_sync_session() as db:
            # Find deliveries that need retry
            failed_deliveries = db.query(WebhookDelivery).filter(
                WebhookDelivery.status == WebhookStatus.FAILED,
                WebhookDelivery.retry_count < WebhookDelivery.max_retries,
                WebhookDelivery.next_retry_at <= datetime.utcnow()
            ).all()
            
            retry_count = 0
            for delivery in failed_deliveries:
                retry_webhook_delivery_task.delay(str(delivery.id))
                retry_count += 1
            
            logger.info(f"Scheduled retry for {retry_count} webhook deliveries")
            return {"retried": retry_count}
            
    except Exception as e:
        logger.error(f"Failed to schedule webhook retries: {e}")
        return {"error": str(e)}