import logging

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config import settings
from app.senders.base import NotificationSender

logger = logging.getLogger(__name__)


class SendGridSender(NotificationSender):
    def __init__(self):
        self._client = SendGridAPIClient(settings.SENDGRID_API_KEY)

    async def send(self, recipient: str, subject: str, body: str, metadata: dict) -> dict:
        html_body = metadata.get("html_body", body)

        message = Mail(
            from_email=(settings.SENDGRID_FROM_EMAIL, settings.SENDGRID_FROM_NAME),
            to_emails=recipient,
            subject=subject,
            html_content=html_body,
            plain_text_content=body,
        )

        if settings.SENDGRID_SANDBOX:
            message.mail_settings = {"sandbox_mode": {"enable": True}}

        response = self._client.send(message)

        logger.info(
            "email_sent",
            extra={
                "recipient": f"***{recipient[-4:]}",
                "status_code": response.status_code,
                "sandbox": settings.SENDGRID_SANDBOX,
            },
        )

        return {"status_code": response.status_code, "headers": dict(response.headers)}
