import logging

from app.kafka.dispatcher import register
from app.schemas.events import EventEnvelope
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


@register("user.welcome")
async def handle_user_welcome(envelope: EventEnvelope, svc: NotificationService) -> None:
    logger.info("handling_user_welcome", extra={"event_id": envelope.event_id})
    await svc.process_event(envelope)


@register("user.password_reset")
async def handle_user_password_reset(envelope: EventEnvelope, svc: NotificationService) -> None:
    logger.info("handling_user_password_reset", extra={"event_id": envelope.event_id})
    await svc.process_event(envelope)


@register("user.email_verification")
async def handle_user_email_verification(envelope: EventEnvelope, svc: NotificationService) -> None:
    logger.info("handling_user_email_verification", extra={"event_id": envelope.event_id})
    await svc.process_event(envelope)
