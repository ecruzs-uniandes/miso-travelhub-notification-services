import logging

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.internal import (
    InternalNotificationRequest,
    InternalNotificationResponse,
    WelcomeRegistrationRequest,
    WelcomeRegistrationResponse,
)
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["internal"])


def verify_internal_token(x_internal_token: str = Header(..., alias="X-Internal-Token")):
    if x_internal_token != settings.INTERNAL_NOTIFY_TOKEN:
        raise HTTPException(status_code=401, detail="Token interno inválido")


@router.post(
    "/notifications/internal",
    response_model=InternalNotificationResponse,
    status_code=202,
    dependencies=[Depends(verify_internal_token)],
)
async def internal_notify(
    request: InternalNotificationRequest,
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        "internal_notify_received",
        extra={"type": request.type, "hotel_id": str(request.hotel_id)},
    )

    service = NotificationService(db)
    try:
        notification_id, channels_sent = await service.send_internal(request)
    except Exception as exc:
        logger.error("internal_notify_failed", extra={"error": str(exc)})
        raise HTTPException(status_code=500, detail="Error al enviar notificación interna")

    return InternalNotificationResponse(
        notification_id=notification_id,
        channels_sent=channels_sent,
    )


@router.post(
    "/notifications/internal/welcome",
    response_model=WelcomeRegistrationResponse,
    status_code=202,
    dependencies=[Depends(verify_internal_token)],
    summary="Welcome email tras registro (lo invoca user-services)",
)
async def internal_welcome(
    request: WelcomeRegistrationRequest,
    db: AsyncSession = Depends(get_db),
):
    logger.info(
        "internal_welcome_received user_id=%s email=***%s",
        str(request.user_id),
        request.email[-4:],
    )

    service = NotificationService(db)
    try:
        notification_id, channels_sent = await service.send_welcome_on_register(
            user_id=request.user_id,
            email=request.email,
            full_name=request.full_name,
        )
        await db.commit()
    except Exception as exc:
        logger.error(
            "internal_welcome_failed user_id=%s error=%s",
            str(request.user_id),
            str(exc),
            exc_info=True,
        )
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error enviando welcome: {exc}")

    return WelcomeRegistrationResponse(
        notification_id=notification_id,
        channels_sent=channels_sent,
    )
