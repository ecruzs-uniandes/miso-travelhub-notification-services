import pytest


class TestDispatcher:
    def test_booking_confirmed_handler_registered(self):
        from app.kafka.dispatcher import get_handler
        handler = get_handler("booking.confirmed")
        assert handler is not None

    def test_booking_cancelled_handler_registered(self):
        from app.kafka.dispatcher import get_handler
        handler = get_handler("booking.cancelled")
        assert handler is not None

    def test_booking_reminder_handler_registered(self):
        from app.kafka.dispatcher import get_handler
        handler = get_handler("booking.reminder")
        assert handler is not None

    def test_payment_completed_handler_registered(self):
        from app.kafka.dispatcher import get_handler
        handler = get_handler("payment.completed")
        assert handler is not None

    def test_payment_failed_handler_registered(self):
        from app.kafka.dispatcher import get_handler
        handler = get_handler("payment.failed")
        assert handler is not None

    def test_user_welcome_handler_registered(self):
        from app.kafka.dispatcher import get_handler
        handler = get_handler("user.welcome")
        assert handler is not None

    def test_unknown_event_returns_none(self):
        from app.kafka.dispatcher import get_handler
        handler = get_handler("unknown.event_type")
        assert handler is None

    def test_unknown_event_does_not_raise(self):
        from app.kafka.dispatcher import get_handler
        try:
            get_handler("completely.unknown")
        except Exception:
            pytest.fail("get_handler raised an exception for unknown event type")
