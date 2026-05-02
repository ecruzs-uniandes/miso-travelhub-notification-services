from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr


class PreferenceUpdate(BaseModel):
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    sms_enabled: bool | None = None
    whatsapp_enabled: bool | None = None
    email_address: str | None = None
    phone_number: str | None = None
    fcm_token: str | None = None


class PreferenceOut(BaseModel):
    user_id: UUID
    email_enabled: bool
    push_enabled: bool
    sms_enabled: bool
    whatsapp_enabled: bool
    email_address: str | None = None
    phone_number: str | None = None
    fcm_token: str | None = None
    locale: str
    updated_at: datetime

    model_config = {"from_attributes": True}
