import uuid

import pytest


class TestPreferenceService:
    @pytest.mark.asyncio
    async def test_get_or_create_creates_defaults(self, db_session):
        from app.services.preference_service import PreferenceService
        svc = PreferenceService(db_session)
        user_id = uuid.uuid4()
        pref = await svc.get_or_create(user_id)

        assert pref.user_id == user_id
        assert pref.email_enabled is True
        assert pref.push_enabled is True
        assert pref.sms_enabled is False
        assert pref.whatsapp_enabled is False
        assert pref.locale == "es"

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing(self, db_session):
        from app.services.preference_service import PreferenceService
        svc = PreferenceService(db_session)
        user_id = uuid.uuid4()

        pref1 = await svc.get_or_create(user_id)
        pref1.email_address = "test@example.com"
        await db_session.flush()

        pref2 = await svc.get_or_create(user_id)
        assert pref2.email_address == "test@example.com"

    @pytest.mark.asyncio
    async def test_update_preference(self, db_session):
        from app.schemas.preference import PreferenceUpdate
        from app.services.preference_service import PreferenceService

        svc = PreferenceService(db_session)
        user_id = uuid.uuid4()
        await svc.get_or_create(user_id)

        data = PreferenceUpdate(email_enabled=False, email_address="nuevo@example.com")
        pref = await svc.update(user_id, data)

        assert pref.email_enabled is False
        assert pref.email_address == "nuevo@example.com"
