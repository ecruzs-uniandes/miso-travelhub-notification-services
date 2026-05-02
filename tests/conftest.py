import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="function")
async def db_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture(scope="function")
async def async_client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def sample_user_id():
    return uuid.UUID("550e8400-e29b-41d4-a716-446655440000")


@pytest.fixture
def sample_hotel_id():
    return uuid.UUID("660e8400-e29b-41d4-a716-446655440001")


@pytest.fixture
def valid_jwt_payload(sample_user_id):
    from jose import jwt
    payload = {
        "sub": str(sample_user_id),
        "role": "traveler",
        "iss": "https://auth.travelhub.app",
        "aud": "travelhub-api",
    }
    token = jwt.encode(payload, key="secret", algorithm="HS256")
    return token


@pytest.fixture
def hotel_admin_jwt_payload(sample_user_id):
    from jose import jwt
    payload = {
        "sub": str(sample_user_id),
        "role": "hotel_admin",
        "iss": "https://auth.travelhub.app",
        "aud": "travelhub-api",
    }
    token = jwt.encode(payload, key="secret", algorithm="HS256")
    return token
