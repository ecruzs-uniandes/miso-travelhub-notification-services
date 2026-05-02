import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import Notification, NotificationLog
from app.models.preference import NotificationPreference
from app.resilience.circuit_breaker import get_circuit_breaker
from app.senders.factory import get_sender
from app.schemas.events import EventEnvelope
from app.schemas.internal import InternalNotificationRequest
from app.services.preference_service import PreferenceService
from app.services.template_service import TemplateService

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.template_svc = TemplateService()
        self.pref_svc = PreferenceService(db)

    async def process_event(self, envelope: EventEnvelope) -> None:
        pref = await self.pref_svc.get_or_create(envelope.user_id)
        event_type_key = envelope.event_type.replace(".", "_")

        channels = self._enabled_channels(pref)
        if not channels:
            logger.info("no_channels_enabled", extra={"user_id": str(envelope.user_id)})
            return

        context = self._build_context(pref, envelope)
        title, body = self._render_title_body(event_type_key, context)

        notification = Notification(
            user_id=envelope.user_id,
            event_type=envelope.event_type,
            title=title,
            body=body,
            metadata_=envelope.payload,
        )
        self.db.add(notification)
        await self.db.flush()

        for channel in channels:
            await self._send_channel(
                notification=notification,
                event_id=envelope.event_id,
                channel=channel,
                event_type_key=event_type_key,
                context=context,
                pref=pref,
            )

    async def send_internal(
        self, request: InternalNotificationRequest
    ) -> tuple[uuid.UUID, list[str]]:
        pref = await self.pref_svc.get_or_create(request.user_id)
        event_type_key = request.type
        event_id = f"internal_{request.type}_{request.hotel_id}_{uuid.uuid4().hex[:8]}"

        context = {
            "user": {"full_name": "", "email": pref.email_address or ""},
            "event": {"occurred_at_human": datetime.now(timezone.utc).strftime("%d de %B de %Y")},
            "payload": {**request.details, "hotel_id": str(request.hotel_id)},
            "links": {"app_url": settings.APP_URL, "support_email": settings.SUPPORT_EMAIL},
        }

        title, body = self._render_title_body(event_type_key, context)

        notification = Notification(
            user_id=request.user_id,
            event_type=request.type,
            title=title,
            body=body,
            metadata_=request.details,
        )
        self.db.add(notification)
        await self.db.flush()

        channels_sent = []
        if pref.email_enabled and pref.email_address:
            await self._send_channel(
                notification=notification,
                event_id=event_id,
                channel="email",
                event_type_key=event_type_key,
                context=context,
                pref=pref,
            )
            channels_sent.append("email")

        return notification.id, channels_sent

    def _enabled_channels(self, pref: NotificationPreference) -> list[str]:
        channels = []
        if pref.email_enabled and pref.email_address:
            channels.append("email")
        if pref.push_enabled and pref.fcm_token:
            channels.append("push")
        return channels

    def _build_context(self, pref: NotificationPreference, envelope: EventEnvelope) -> dict:
        occurred = envelope.occurred_at
        return {
            "user": {
                "full_name": envelope.payload.get("full_name", ""),
                "email": pref.email_address or "",
            },
            "event": {
                "occurred_at_human": occurred.strftime("%-d de %B de %Y, %-I:%M %p"),
            },
            "payload": envelope.payload,
            "links": {
                "app_url": settings.APP_URL,
                "support_email": settings.SUPPORT_EMAIL,
            },
        }

    def _render_title_body(self, event_type_key: str, context: dict) -> tuple[str, str]:
        txt_template = f"{event_type_key}.email.txt"
        svc = self.template_svc
        if svc.template_exists(txt_template):
            body = svc.render(txt_template, context)
        else:
            body = f"Notificación: {event_type_key}"

        title_map = {
            "booking_confirmed": "Tu reserva está confirmada",
            "booking_cancelled": "Tu reserva ha sido cancelada",
            "booking_reminder": "Recordatorio de tu reserva",
            "payment_completed": "Pago completado exitosamente",
            "payment_failed": "Error en el pago",
            "user_welcome": "¡Bienvenido a TravelHub!",
            "user_password_reset": "Restablece tu contraseña",
            "pms_sync_conflict": "Conflicto de sincronización PMS",
            "pms_sync_error": "Error de sincronización PMS",
            "pms_sync_complete": "Sincronización PMS completada",
        }
        title = title_map.get(event_type_key, f"Notificación: {event_type_key}")
        return title, body.strip()

    async def _send_channel(
        self,
        notification: Notification,
        event_id: str,
        channel: str,
        event_type_key: str,
        context: dict,
        pref: NotificationPreference,
    ) -> None:
        template_code = f"{event_type_key}.{channel}"

        # Idempotency check: skip if already processed
        existing_result = await self.db.execute(
            select(NotificationLog).where(
                NotificationLog.event_id == event_id,
                NotificationLog.channel == channel,
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            logger.info(
                "notification_idempotent_skip",
                extra={"event_id": event_id, "channel": channel},
            )
            return

        log_entry = NotificationLog(
            notification_id=notification.id,
            event_id=event_id,
            channel=channel,
            template_code=template_code,
            status="pending",
            attempts=0,
        )
        self.db.add(log_entry)
        await self.db.flush()

        recipient = pref.email_address if channel == "email" else (pref.fcm_token or "")
        subject = notification.title

        try:
            send_metadata = {**context.get("payload", {})}
            if channel == "email":
                html_template = f"{event_type_key}.email.html"
                if self.template_svc.template_exists(html_template):
                    send_metadata["html_body"] = self.template_svc.render(html_template, context)

            provider_response = await self._send_with_retry(
                channel=channel,
                recipient=recipient,
                subject=subject,
                body=notification.body,
                metadata=send_metadata,
            )

            log_entry.status = "sent"
            log_entry.provider_response = provider_response
            log_entry.sent_at = datetime.now(timezone.utc)
            log_entry.attempts += 1

        except NotImplementedError:
            log_entry.status = "skipped"
            log_entry.error_message = "Provider not implemented for MVP"
        except Exception as exc:
            logger.error(
                "notification_send_failed",
                extra={"channel": channel, "event_id": event_id, "error": str(exc)},
            )
            log_entry.status = "failed"
            log_entry.error_message = str(exc)

        await self.db.flush()

    async def _send_with_retry(
        self, channel: str, recipient: str, subject: str, body: str, metadata: dict
    ) -> dict:
        sender = get_sender(channel)
        cb = get_circuit_breaker(f"sender_{channel}")
        max_attempts = settings.RETRY_MAX_ATTEMPTS
        backoff_base = settings.RETRY_BACKOFF_BASE
        last_exc: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                return await cb.call(sender.send, recipient, subject, body, metadata)
            except NotImplementedError:
                raise
            except Exception as exc:
                last_exc = exc
                if attempt < max_attempts:
                    await asyncio.sleep(backoff_base ** attempt)

        raise last_exc
