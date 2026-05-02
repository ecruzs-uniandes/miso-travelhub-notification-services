import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.preference import NotificationPreference
from app.schemas.preference import PreferenceUpdate


class PreferenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, user_id: uuid.UUID) -> NotificationPreference:
        result = await self.db.execute(
            select(NotificationPreference).where(NotificationPreference.user_id == user_id)
        )
        pref = result.scalar_one_or_none()

        if not pref:
            pref = NotificationPreference(user_id=user_id)
            self.db.add(pref)
            await self.db.flush()

        return pref

    async def update(self, user_id: uuid.UUID, data: PreferenceUpdate) -> NotificationPreference:
        pref = await self.get_or_create(user_id)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(pref, field, value)

        pref.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return pref
