from app.senders.base import NotificationSender
from app.senders.email_sendgrid import SendGridSender
from app.senders.push_fcm import FCMSender
from app.senders.sms_stub import SMSStubSender
from app.senders.whatsapp_stub import WhatsAppStubSender

_registry: dict[str, NotificationSender] = {}


def get_sender(channel: str) -> NotificationSender:
    if channel not in _registry:
        _registry["email"] = SendGridSender()
        _registry["push"] = FCMSender()
        _registry["sms"] = SMSStubSender()
        _registry["whatsapp"] = WhatsAppStubSender()

    sender = _registry.get(channel)
    if not sender:
        raise ValueError(f"Canal desconocido: {channel}")
    return sender
