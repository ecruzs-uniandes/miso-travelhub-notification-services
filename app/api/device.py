import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["device"])


class RegisterDeviceRequest(BaseModel):
    fcm_token: str = Field(..., min_length=1)
    platform: str = Field(..., min_length=1)


@router.post("/notifications/register-device")
async def register_device(
    body: RegisterDeviceRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("UPDATE users SET fcm_token = :fcm_token WHERE id = :user_id"),
        {"fcm_token": body.fcm_token, "user_id": current_user.user_id},
    )

    return {
        "status": "ok",
        "message": "Dispositivo registrado correctamente"
    }
