from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr


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
