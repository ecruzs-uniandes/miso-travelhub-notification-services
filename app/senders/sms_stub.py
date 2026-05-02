import logging

from app.senders.base import NotificationSender

logger = logging.getLogger(__name__)


class SMSStubSender(NotificationSender):
    async def send(self, recipient: str, subject: str, body: str, metadata: dict) -> dict:
        logger.warning(
            "sms_stub_invoked",
            extra={"recipient": "***", "body_len": len(body)},
        )
        raise NotImplementedError("SMS provider not configured for MVP")
