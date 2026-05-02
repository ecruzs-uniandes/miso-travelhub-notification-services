import uuid
from unittest.mock import AsyncMock, patch

import pytest

from tests.fixtures.sample_events import (
    BOOKING_CONFIRMED_EVENT,
    PAYMENT_COMPLETED_EVENT,
    USER_WELCOME_EVENT,
)


class TestKafkaHandlers:
    @pytest.mark.asyncio
    async def test_booking_confirmed_creates_notification(self, db_session, sample_user_id):
        from sqlalchemy import select

        from app.models.notification import Notification, NotificationLog
        from app.models.preference import NotificationPreference
        from app.schemas.events import EventEnvelope
        from app.services.notification_service import NotificationService

        pref = NotificationPreference(
            user_id=sample_user_id,
            email_enabled=True,
            email_address="test@example.com",
        )
        db_session.add(pref)
        await db_session.flush()

        event = dict(BOOKING_CONFIRMED_EVENT)
        event["user_id"] = str(sample_user_id)
        event["event_id"] = "evt_test_booking_001"
        envelope = EventEnvelope(**event)

        with patch("app.services.notification_service.get_sender") as mock_factory:
            mock_sender = AsyncMock()
            mock_sender.send.return_value = {"status_code": 202}
            mock_factory.return_value = mock_sender

            with patch("app.resilience.circuit_breaker.get_circuit_breaker") as mock_cb:
                mock_breaker = AsyncMock()
                mock_breaker.call = AsyncMock(return_value={"status_code": 202})
                mock_cb.return_value = mock_breaker

                svc = NotificationService(db_session)
                await svc.process_event(envelope)
                await db_session.flush()

        result = await db_session.execute(
            select(Notification).where(Notification.user_id == sample_user_id)
        )
        notifications = result.scalars().all()
        assert len(notifications) == 1
        assert notifications[0].event_type == "booking.confirmed"

    @pytest.mark.asyncio
    async def test_idempotency_same_event_id(self, db_session, sample_user_id):
        from sqlalchemy import select

        from app.models.notification import Notification, NotificationLog
        from app.models.preference import NotificationPreference
        from app.schemas.events import EventEnvelope
        from app.services.notification_service import NotificationService

        pref = NotificationPreference(
            user_id=sample_user_id,
            email_enabled=True,
            email_address="test@example.com",
        )
        db_session.add(pref)
        await db_session.flush()

        event = dict(BOOKING_CONFIRMED_EVENT)
        event["user_id"] = str(sample_user_id)
        event["event_id"] = "evt_idempotent_test"
        envelope = EventEnvelope(**event)

        with patch("app.resilience.circuit_breaker.get_circuit_breaker") as mock_cb:
            mock_breaker = AsyncMock()
            mock_breaker.call = AsyncMock(return_value={"status_code": 202})
            mock_cb.return_value = mock_breaker

            svc = NotificationService(db_session)
            await svc.process_event(envelope)
            await db_session.flush()

            await svc.process_event(envelope)
            await db_session.flush()

        result = await db_session.execute(
            select(NotificationLog).where(NotificationLog.event_id == "evt_idempotent_test")
        )
        logs = result.scalars().all()
        assert len(logs) == 1
