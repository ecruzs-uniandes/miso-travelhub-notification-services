import uuid

import pytest
from jose import jwt


class TestPublicAPI:
    def _make_token(self, user_id, role="traveler"):
        return jwt.encode({"sub": str(user_id), "role": role}, key="secret", algorithm="HS256")

    @pytest.mark.asyncio
    async def test_get_notifications_no_auth_returns_401(self, async_client):
        resp = await async_client.get("/api/v1/notifications")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_get_notifications_invalid_role_returns_403(self, async_client):
        token = jwt.encode({"sub": str(uuid.uuid4()), "role": "unknown"}, key="s", algorithm="HS256")
        resp = await async_client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_get_notifications_empty_list(self, async_client, sample_user_id):
        token = self._make_token(sample_user_id)
        resp = await async_client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_notifications_pagination(self, async_client, db_session, sample_user_id):
        from app.models.notification import Notification

        for i in range(5):
            n = Notification(
                user_id=sample_user_id,
                event_type="booking.confirmed",
                title=f"Notif {i}",
                body=f"Cuerpo {i}",
            )
            db_session.add(n)
        await db_session.flush()

        token = self._make_token(sample_user_id)
        resp = await async_client.get(
            "/api/v1/notifications?limit=3&offset=0",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_get_preferences_creates_default(self, async_client, sample_user_id):
        token = self._make_token(sample_user_id)
        resp = await async_client.get(
            "/api/v1/notifications/preferences",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_enabled"] is True
        assert data["push_enabled"] is True

    @pytest.mark.asyncio
    async def test_update_preferences(self, async_client, sample_user_id):
        token = self._make_token(sample_user_id)
        resp = await async_client.put(
            "/api/v1/notifications/preferences",
            json={"email_enabled": False, "email_address": "test@example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email_enabled"] is False
        assert data["email_address"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_mark_as_read(self, async_client, db_session, sample_user_id):
        from app.models.notification import Notification

        n = Notification(
            user_id=sample_user_id,
            event_type="booking.confirmed",
            title="Test",
            body="Body",
        )
        db_session.add(n)
        await db_session.flush()

        token = self._make_token(sample_user_id)
        resp = await async_client.post(
            f"/api/v1/notifications/{n.id}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["read_at"] is not None

    @pytest.mark.asyncio
    async def test_unread_only_filter(self, async_client, db_session, sample_user_id):
        from datetime import datetime, timezone

        from app.models.notification import Notification

        read_n = Notification(
            user_id=sample_user_id,
            event_type="booking.confirmed",
            title="Read",
            body="body",
            read_at=datetime.now(timezone.utc),
        )
        unread_n = Notification(
            user_id=sample_user_id,
            event_type="payment.completed",
            title="Unread",
            body="body",
        )
        db_session.add_all([read_n, unread_n])
        await db_session.flush()

        token = self._make_token(sample_user_id)
        resp = await async_client.get(
            "/api/v1/notifications?unread_only=true",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Unread"
