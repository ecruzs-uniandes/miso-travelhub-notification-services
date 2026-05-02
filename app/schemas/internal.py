from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class InternalNotificationRequest(BaseModel):
    type: Literal["pms_sync_conflict", "pms_sync_error", "pms_sync_complete"]
    user_id: UUID
    hotel_id: UUID
    details: dict
    recipients: list[str] = ["hotel_admin"]


class InternalNotificationResponse(BaseModel):
    notification_id: UUID
    channels_sent: list[str]
