from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class InternalNotificationRequest(BaseModel):
    type: Literal["pms_sync_conflict", "pms_sync_error", "pms_sync_complete"]
    user_id: UUID
    hotel_id: UUID
    details: dict
    recipients: list[str] = ["hotel_admin"]


class InternalNotificationResponse(BaseModel):
    notification_id: UUID
    channels_sent: list[str]


class WelcomeRegistrationRequest(BaseModel):
    """Disparado por user-services tras un registro exitoso. Envía welcome
    incondicionalmente (no chequea preferencias — es flujo de onboarding).
    Como side-effect, también upsertea notification_preference con email_enabled
    y email_address para que cualquier evento futuro (booking, payment) llegue
    sin que el user tenga que configurar nada."""

    user_id: UUID
    email: EmailStr
    full_name: str


class WelcomeRegistrationResponse(BaseModel):
    notification_id: UUID
    channels_sent: list[str]


class EventIngestionRequest(BaseModel):
    """Envelope simplificado para ingesta HTTP de eventos.

    Los workers de cada dominio (booking, payment, user) llaman aquí con sólo
    `event_type`, `user_id` y `payload`. El servicio genera internamente
    `event_id` (para la fila en `notification_log`) y `occurred_at` (UTC).
    La deduplicación / idempotencia es responsabilidad del worker — si llaman
    dos veces, se envían dos correos.
    """

    event_type: str = Field(
        ..., description="Tipo de evento. Ej: booking.confirmed, payment.completed, user.welcome."
    )
    user_id: UUID
    payload: dict = Field(default_factory=dict)


class EventIngestionResponse(BaseModel):
    accepted: bool
    event_id: str = Field(
        ..., description="ID generado por el servicio. Útil para trazar en logs."
    )
    event_type: str
    user_id: UUID
