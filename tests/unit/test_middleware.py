import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


class TestJWTMiddleware:
    @pytest.mark.asyncio
    async def test_health_no_jwt_required(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/health")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_notifications_without_jwt_returns_401(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_notifications_with_invalid_role_returns_403(self):
        from jose import jwt
        token = jwt.encode(
            {"sub": "some-uuid", "role": "unknown_role"},
            key="secret",
            algorithm="HS256",
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/notifications",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403


class TestRateLimitMiddleware:
    @pytest.mark.asyncio
    async def test_health_not_rate_limited(self):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            for _ in range(5):
                resp = await client.get("/health")
            assert resp.status_code == 200
