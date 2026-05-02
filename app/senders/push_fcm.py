import json
import logging

from app.config import settings
from app.senders.base import NotificationSender

logger = logging.getLogger(__name__)


class FCMSender(NotificationSender):
    _initialized = False

    def _ensure_init(self):
        if FCMSender._initialized:
            return
        import firebase_admin
        from firebase_admin import credentials

        creds_path = settings.FCM_CREDENTIALS_JSON
        if creds_path and creds_path.endswith(".json"):
            cred = credentials.Certificate(creds_path)
        elif creds_path:
            try:
                cred_dict = json.loads(creds_path)
                cred = credentials.Certificate(cred_dict)
            except (json.JSONDecodeError, ValueError):
                logger.warning("fcm_credentials_invalid_skipping")
                return
        else:
            logger.warning("fcm_credentials_not_configured")
            return

        if not firebase_admin._apps:
            firebase_admin.initialize_app(cred)
        FCMSender._initialized = True

    async def send(self, recipient: str, subject: str, body: str, metadata: dict) -> dict:
        if not recipient:
            logger.info("fcm_token_empty_skipping")
            return {"status": "skipped", "reason": "no_fcm_token"}

        self._ensure_init()

        if not FCMSender._initialized:
            return {"status": "skipped", "reason": "fcm_not_configured"}

        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(title=subject, body=body),
            data=metadata.get("data", {}),
            token=recipient,
        )

        response = messaging.send(message)
        logger.info("push_sent", extra={"message_id": response})
        return {"message_id": response}
