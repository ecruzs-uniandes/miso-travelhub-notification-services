from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class EventEnvelope(BaseModel):
    event_id: str
    event_type: str
    occurred_at: datetime
    user_id: UUID
    payload: dict


class BookingConfirmedPayload(BaseModel):
    booking_id: UUID
    hotel_name: str
    check_in: datetime
    check_out: datetime
    total: float
    currency: str


class BookingCancelledPayload(BaseModel):
    booking_id: UUID
    hotel_name: str
    check_in: datetime
    check_out: datetime
    reason: str | None = None


class BookingReminderPayload(BaseModel):
    booking_id: UUID
    hotel_name: str
    check_in: datetime
    check_out: datetime
    days_until: int


class PaymentCompletedPayload(BaseModel):
    payment_id: UUID
    booking_id: UUID
    amount: float
    currency: str
    provider: Literal["stripe", "mercadopago", "paypal"]


class PaymentFailedPayload(BaseModel):
    payment_id: UUID
    booking_id: UUID
    amount: float
    currency: str
    reason: str | None = None


class UserWelcomePayload(BaseModel):
    email: str
    full_name: str


class UserPasswordResetPayload(BaseModel):
    email: str
    full_name: str
    reset_token: str
    reset_url: str


class UserEmailVerificationPayload(BaseModel):
    email: str
    full_name: str
    verification_token: str
    verification_url: str
