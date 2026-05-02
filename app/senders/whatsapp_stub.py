import logging

from app.senders.base import NotificationSender

logger = logging.getLogger(__name__)


class WhatsAppStubSender(NotificationSender):
    async def send(self, recipient: str, subject: str, body: str, metadata: dict) -> dict:
        logger.warning(
            "whatsapp_stub_invoked",
            extra={"recipient": "***", "body_len": len(body)},
        )
        raise NotImplementedError("WhatsApp provider not configured for MVP")
