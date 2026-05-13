from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Tipos que viajan por Kafka (booking-events, payment-events, user-events).
# Los pms_sync_* NO van aquí — se disparan por POST /api/v1/notifications/internal.
KafkaEventType = Literal[
    "booking.confirmed",
    "booking.cancelled",
    "booking.reminder",
    "payment.completed",
    "payment.failed",
    "user.welcome",
    "user.password_reset",
]


class AdminTestEventRequest(BaseModel):
    """Simula un evento Kafka sin pasar por el broker. Para QA solamente."""

    event_type: KafkaEventType = Field(
        ...,
        description="Tipo de evento Kafka a simular. Lista cerrada de 7 tipos.",
    )
    user_id: UUID = Field(
        ...,
        description="UUID del destinatario. Debe tener preferencias configuradas en notification_preference.",
    )
    payload: dict = Field(
        default_factory=dict,
        description="Payload específico del event_type (ver schemas/events.py).",
    )


class AdminTestEventResponse(BaseModel):
    accepted: bool
    event_id: str
    event_type: str
    user_id: UUID
