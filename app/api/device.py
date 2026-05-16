import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.senders.push_fcm import FCMSender

logger = logging.getLogger(__name__)
router = APIRouter(tags=["device"])

class RegisterDeviceRequest(BaseModel):
    fcm_token: str = Field(..., min_length=1)
    platform: str = Field(..., min_length=1)


class SendNotificationRequest(BaseModel):
    booking_id: uuid.UUID
    status: Literal["PAID", "CONFIRMED", "CANCELED", "REFUNDED"]


STATUS_LABELS = {
    "PAID": "PAGADA",
    "CONFIRMED": "CONFIRMADA",
    "CANCELED": "CANCELADA",
    "REFUNDED": "REEMBOLSADA",
}

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

@router.post("/notifications/unregister-device")
async def unregister_device(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("UPDATE users SET fcm_token = '' WHERE id = :user_id"),
        {"user_id": current_user.user_id},
    )

    return {
        "status": "ok",
        "message": "Dispositivo desvinculado correctamente"
    }

@router.post("/notifications/send-notification")
async def send_notification(
    body: SendNotificationRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("SELECT viajeroId FROM reserva WHERE id = :booking_id"),
        {"booking_id": body.booking_id},
    )
    row = result.first()
    viajero_id = row[0] if row else None

    if not viajero_id:
        raise HTTPException(
            status_code=404,
            detail="La reserva no existe",
        )

    result = await db.execute(
        text("SELECT fcm_token FROM users WHERE id = :user_id"),
        {"user_id": viajero_id},
    )
    row = result.first()
    fcm_token = row[0] if row else None

    if not fcm_token:
        raise HTTPException(
            status_code=404,
            detail="El usuario no tiene un dispositivo registrado",
        )

    status_label = STATUS_LABELS[body.status]
    notification_detail = f"Cambio de estado en tu reserva: {status_label}"

    sender = FCMSender()
    provider_response = await sender.send(
        recipient=fcm_token,
        subject="TravelHub",
        body=notification_detail,
        metadata={"data": {"booking_id": str(body.booking_id)}},
    )

    sent_ok = (
        provider_response.get("status") != "skipped"
        and "message_id" in provider_response
    )

    return {
        "status": "ok" if sent_ok else "skipped",
        "message": "Notificación enviada" if sent_ok else "Notificación omitida",
        "provider_response": provider_response,
    }