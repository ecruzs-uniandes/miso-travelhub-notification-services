import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
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

    async def ensure_welcome_preference(self, user_id: uuid.UUID, email: str) -> None:
        """Upsertea la preferencia del user con email_address + email_enabled=true.

        Usado en el flujo de welcome (HTTP /internal/welcome y handler Kafka
        user.welcome): un user recién registrado no tiene preferencia, así que
        forzamos su creación con el email del payload para que process_event
        pueda enviarle el welcome (y cualquier evento futuro) por email.
        """
        pref = await self.pref_svc.get_or_create(user_id)
        if pref.email_address != email or not pref.email_enabled:
            pref.email_address = email
            pref.email_enabled = True
            pref.updated_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def send_welcome_on_register(
        self, user_id: uuid.UUID, email: str, full_name: str
    ) -> tuple[uuid.UUID, list[str]]:
        """Welcome incondicional (no respeta preferencias del user).

        Lo invoca user-services vía HTTP /internal/welcome (alternativa síncrona
        para pruebas / fallback). El flujo "correcto" pasa por Kafka — ver
        handle_user_welcome en app/kafka/handlers/user.py.
        """
        await self.ensure_welcome_preference(user_id, email)

        # event_id incluye timestamp para que reintentos tras fallos NO sean
        # bloqueados por idempotencia (otros eventos como booking sí mantienen
        # event_id estable porque vienen de Kafka con event_id propio).
        ts = int(datetime.now(timezone.utc).timestamp())
        envelope = EventEnvelope(
            event_id=f"register_welcome_{user_id}_{ts}",
            event_type="user.welcome",
            occurred_at=datetime.now(timezone.utc),
            user_id=user_id,
            payload={"email": email, "full_name": full_name},
        )
        await self.process_event(envelope)

        # Retornar el id de la notificación creada por process_event
        result = await self.db.execute(
            select(NotificationLog.notification_id, NotificationLog.channel)
            .where(NotificationLog.event_id == envelope.event_id)
        )
        rows = list(result.all())
        if not rows:
            # Edge case: process_event no creó nada (shouldn't happen con pref forzada)
            raise RuntimeError("welcome event processing did not produce notification log")
        notification_id = rows[0].notification_id
        channels_sent = [r.channel for r in rows]
        return notification_id, channels_sent

    async def process_event(self, envelope: EventEnvelope) -> None:
        pref = await self.pref_svc.get_or_create(envelope.user_id)
        event_type_key = envelope.event_type.replace(".", "_")

        effective_email, effective_full_name = await self._resolve_user_info(
            pref, envelope.payload
        )
        channels = self._enabled_channels(pref, effective_email)
        if not channels:
            logger.info(
                "no_channels_enabled",
                extra={"user_id": str(envelope.user_id)},
            )
            return

        context = self._build_context(envelope, effective_email, effective_full_name)
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
                effective_email=effective_email,
            )

    async def send_internal(
        self, request: InternalNotificationRequest
    ) -> tuple[uuid.UUID, list[str]]:
        pref = await self.pref_svc.get_or_create(request.user_id)
        event_type_key = request.type
        event_id = f"internal_{request.type}_{request.hotel_id}_{uuid.uuid4().hex[:8]}"

        effective_email, effective_full_name = await self._resolve_user_info(pref, {})

        context = {
            "user": {"full_name": effective_full_name, "email": effective_email or ""},
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
        if pref.email_enabled and effective_email:
            await self._send_channel(
                notification=notification,
                event_id=event_id,
                channel="email",
                event_type_key=event_type_key,
                context=context,
                pref=pref,
                effective_email=effective_email,
            )
            channels_sent.append("email")

        return notification.id, channels_sent

    async def _resolve_user_info(
        self, pref: NotificationPreference, payload: dict
    ) -> tuple[str | None, str]:
        """Resuelve email + full_name efectivos para el envío.

        Precedencia (opt-out):
        1. `notification_preference.email_address` si está seteado.
        2. Fallback: `users.email` (misma BD `travelhub`, columna gestionada por
           user-services). Solo se consulta si la preferencia no tiene email,
           para evitar un SELECT extra cuando el usuario ya configuró el suyo.

        Para `full_name`: prioriza `payload.full_name` (lo trae el productor en
        `user.welcome`); si no, cae al `users.nombre`.
        """
        email = pref.email_address or None
        full_name = (payload or {}).get("full_name", "")

        if email and full_name:
            return email, full_name

        # Query directa a `users` (tabla owned por user-services, misma BD).
        # Si la tabla no existe (tests con SQLite in-memory) o la query falla,
        # retornamos lo que tengamos sin romper el flujo.
        try:
            result = await self.db.execute(
                text("SELECT email, nombre FROM users WHERE id = :uid AND activo = true"),
                {"uid": str(pref.user_id)},
            )
            row = result.first()
            if row:
                if not email:
                    email = row.email
                if not full_name:
                    full_name = row.nombre
        except Exception as exc:
            logger.debug(
                "user_lookup_fallback_failed user_id=%s error=%s",
                str(pref.user_id),
                str(exc),
            )

        return email, full_name

    def _enabled_channels(
        self, pref: NotificationPreference, effective_email: str | None
    ) -> list[str]:
        channels = []
        if pref.email_enabled and effective_email:
            channels.append("email")
        if pref.push_enabled and pref.fcm_token:
            channels.append("push")
        return channels

    def _build_context(
        self,
        envelope: EventEnvelope,
        effective_email: str | None,
        effective_full_name: str,
    ) -> dict:
        occurred = envelope.occurred_at
        return {
            "user": {
                "full_name": effective_full_name,
                "email": effective_email or "",
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
        effective_email: str | None = None,
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

        recipient = (effective_email or pref.email_address or "") if channel == "email" else (pref.fcm_token or "")
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
                "notification_send_failed channel=%s event_id=%s error=%s",
                channel,
                event_id,
                str(exc),
                exc_info=True,
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
