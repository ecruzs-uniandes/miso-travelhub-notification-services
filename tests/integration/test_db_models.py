import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.notification import Notification, NotificationLog
from app.models.preference import NotificationPreference


class TestDBModels:
    @pytest.mark.asyncio
    async def test_create_notification_preference(self, db_session):
        user_id = uuid.uuid4()
        pref = NotificationPreference(user_id=user_id, email_address="test@example.com")
        db_session.add(pref)
        await db_session.flush()

        result = await db_session.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        stored = result.scalar_one()
        assert stored.email_address == "test@example.com"
        assert stored.email_enabled is True

    @pytest.mark.asyncio
    async def test_create_notification(self, db_session):
        user_id = uuid.uuid4()
        n = Notification(
            user_id=user_id,
            event_type="booking.confirmed",
            title="Test",
            body="Body text",
        )
        db_session.add(n)
        await db_session.flush()

        result = await db_session.execute(select(Notification).where(Notification.id == n.id))
        stored = result.scalar_one()
        assert stored.title == "Test"
        assert stored.read_at is None

    @pytest.mark.asyncio
    async def test_notification_log_unique_constraint(self, db_session):
        user_id = uuid.uuid4()
        n = Notification(
            user_id=user_id,
            event_type="booking.confirmed",
            title="Test",
            body="Body",
        )
        db_session.add(n)
        await db_session.flush()

        log1 = NotificationLog(
            notification_id=n.id,
            event_id="evt_unique_test",
            channel="email",
            template_code="booking_confirmed.email",
            status="sent",
        )
        db_session.add(log1)
        await db_session.flush()

        log2 = NotificationLog(
            notification_id=n.id,
            event_id="evt_unique_test",
            channel="email",
            template_code="booking_confirmed.email",
            status="sent",
        )
        db_session.add(log2)

        with pytest.raises(IntegrityError):
            await db_session.flush()

    @pytest.mark.asyncio
    async def test_notification_log_different_channels_allowed(self, db_session):
        user_id = uuid.uuid4()
        n = Notification(
            user_id=user_id,
            event_type="booking.confirmed",
            title="Test",
            body="Body",
        )
        db_session.add(n)
        await db_session.flush()

        log_email = NotificationLog(
            notification_id=n.id,
            event_id="evt_multi_channel",
            channel="email",
            template_code="booking_confirmed.email",
            status="sent",
        )
        log_push = NotificationLog(
            notification_id=n.id,
            event_id="evt_multi_channel",
            channel="push",
            template_code="booking_confirmed.push",
            status="sent",
        )
        db_session.add_all([log_email, log_push])
        await db_session.flush()

        result = await db_session.execute(
            select(NotificationLog).where(NotificationLog.event_id == "evt_multi_channel")
        )
        logs = result.scalars().all()
        assert len(logs) == 2
