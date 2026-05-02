import logging

from app.kafka.dispatcher import register
from app.schemas.events import EventEnvelope
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@register("booking.confirmed")
async def handle_booking_confirmed(envelope: EventEnvelope, svc: NotificationService) -> None:
    logger.info("handling_booking_confirmed", extra={"event_id": envelope.event_id})
    await svc.process_event(envelope)


@register("booking.cancelled")
async def handle_booking_cancelled(envelope: EventEnvelope, svc: NotificationService) -> None:
    logger.info("handling_booking_cancelled", extra={"event_id": envelope.event_id})
    await svc.process_event(envelope)


@register("booking.reminder")
async def handle_booking_reminder(envelope: EventEnvelope, svc: NotificationService) -> None:
    logger.info("handling_booking_reminder", extra={"event_id": envelope.event_id})
    await svc.process_event(envelope)
