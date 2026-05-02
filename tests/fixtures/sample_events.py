import uuid
from datetime import datetime, timezone

SAMPLE_USER_ID = "550e8400-e29b-41d4-a716-446655440000"
SAMPLE_HOTEL_ID = "660e8400-e29b-41d4-a716-446655440001"
SAMPLE_BOOKING_ID = "770e8400-e29b-41d4-a716-446655440002"
SAMPLE_PAYMENT_ID = "880e8400-e29b-41d4-a716-446655440003"

BOOKING_CONFIRMED_EVENT = {
    "event_id": "evt_booking_001",
    "event_type": "booking.confirmed",
    "occurred_at": "2026-05-01T10:00:00Z",
    "user_id": SAMPLE_USER_ID,
    "payload": {
        "booking_id": SAMPLE_BOOKING_ID,
        "hotel_name": "Hotel Bogotá",
        "check_in": "2026-06-15T14:00:00Z",
        "check_out": "2026-06-18T12:00:00Z",
        "total": 450.0,
        "currency": "USD",
    },
}

PAYMENT_COMPLETED_EVENT = {
    "event_id": "evt_payment_001",
    "event_type": "payment.completed",
    "occurred_at": "2026-05-01T10:05:00Z",
    "user_id": SAMPLE_USER_ID,
    "payload": {
        "payment_id": SAMPLE_PAYMENT_ID,
        "booking_id": SAMPLE_BOOKING_ID,
        "amount": 450.0,
        "currency": "USD",
        "provider": "stripe",
    },
}

USER_WELCOME_EVENT = {
    "event_id": "evt_user_001",
    "event_type": "user.welcome",
    "occurred_at": "2026-05-01T09:00:00Z",
    "user_id": SAMPLE_USER_ID,
    "payload": {
        "email": "usuario@example.com",
        "full_name": "Juan Pérez",
    },
}
