import logging

from app.kafka.dispatcher import register
from app.schemas.events import EventEnvelope
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@register("payment.completed")
async def handle_payment_completed(envelope: EventEnvelope, svc: NotificationService) -> None:
    logger.info("handling_payment_completed", extra={"event_id": envelope.event_id})
    await svc.process_event(envelope)


@register("payment.failed")
async def handle_payment_failed(envelope: EventEnvelope, svc: NotificationService) -> None:
    logger.info("handling_payment_failed", extra={"event_id": envelope.event_id})
    await svc.process_event(envelope)
