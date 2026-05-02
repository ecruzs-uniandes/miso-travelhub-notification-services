import uuid
from unittest.mock import AsyncMock, patch

import pytest


class TestInternalAPI:
    @pytest.mark.asyncio
    async def test_missing_token_returns_422(self, async_client):
        resp = await async_client.post(
            "/api/v1/notifications/internal",
            json={
                "type": "pms_sync_conflict",
                "user_id": str(uuid.uuid4()),
                "hotel_id": str(uuid.uuid4()),
                "details": {},
                "recipients": ["hotel_admin"],
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_token_returns_401(self, async_client):
        resp = await async_client.post(
            "/api/v1/notifications/internal",
            json={
                "type": "pms_sync_conflict",
                "user_id": str(uuid.uuid4()),
                "hotel_id": str(uuid.uuid4()),
                "details": {},
                "recipients": ["hotel_admin"],
            },
            headers={"X-Internal-Token": "wrong-token"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_payload_returns_422(self, async_client):
        from app.config import settings
        resp = await async_client.post(
            "/api/v1/notifications/internal",
            json={"type": "invalid_type"},
            headers={"X-Internal-Token": settings.INTERNAL_NOTIFY_TOKEN},
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_valid_request_returns_202(self, async_client):
        from app.config import settings
        from app.services.notification_service import NotificationService

        user_id = uuid.uuid4()
        hotel_id = uuid.uuid4()
        mock_return = (uuid.uuid4(), ["email"])

        with patch.object(NotificationService, "send_internal", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = mock_return
            resp = await async_client.post(
                "/api/v1/notifications/internal",
                json={
                    "type": "pms_sync_conflict",
                    "user_id": str(user_id),
                    "hotel_id": str(hotel_id),
                    "details": {"conflict_type": "availability"},
                    "recipients": ["hotel_admin"],
                },
                headers={"X-Internal-Token": settings.INTERNAL_NOTIFY_TOKEN},
            )

        assert resp.status_code == 202
        data = resp.json()
        assert "notification_id" in data
        assert "channels_sent" in data
