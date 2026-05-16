from datetime import datetime
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
    """Envelope estándar TravelHub para eventos de notificación recibidos vía HTTP.

    Mismo shape que el envelope Kafka histórico (booking-events / payment-events /
    user-events) para que los workers de dominio (booking, payment, user) puedan
    enviar lo que originalmente iba a publicarse al broker.
    """

    event_id: str = Field(..., description="ID único del evento (idempotencia).")
    event_type: str = Field(
        ..., description="Tipo de evento. Ej: booking.confirmed, payment.completed, user.welcome."
    )
    occurred_at: datetime
    user_id: UUID
    payload: dict = Field(default_factory=dict)


class EventIngestionResponse(BaseModel):
    accepted: bool
    event_id: str
    event_type: str
    user_id: UUID
