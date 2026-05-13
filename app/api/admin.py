import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.admin import AdminTestEventRequest, AdminTestEventResponse
from app.schemas.events import EventEnvelope
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])


def verify_admin_enabled():
    if not settings.ADMIN_TEST_ENDPOINT_ENABLED:
        raise HTTPException(status_code=404, detail="Not Found")


def verify_internal_token(x_internal_token: str = Header(..., alias="X-Internal-Token")):
    if x_internal_token != settings.INTERNAL_NOTIFY_TOKEN:
        raise HTTPException(status_code=401, detail="Token interno inválido")


@router.post(
    "/notifications/admin/test-event",
    response_model=AdminTestEventResponse,
    status_code=202,
    dependencies=[Depends(verify_admin_enabled), Depends(verify_internal_token)],
    summary="Dispara un evento Kafka simulado (QA only)",
)
async def admin_test_event(
    request: AdminTestEventRequest,
    db: AsyncSession = Depends(get_db),
):
    envelope = EventEnvelope(
        event_id=f"admin_test_{uuid.uuid4().hex}",
        event_type=request.event_type,
        occurred_at=datetime.now(timezone.utc),
        user_id=request.user_id,
        payload=request.payload,
    )
    logger.info(
        "admin_test_event_received event_type=%s user_id=%s event_id=%s",
        request.event_type,
        request.user_id,
        envelope.event_id,
    )

    service = NotificationService(db)
    try:
        await service.process_event(envelope)
        await db.commit()
    except Exception as exc:
        logger.error(
            "admin_test_event_failed event_type=%s error=%s",
            request.event_type,
            str(exc),
            exc_info=True,
        )
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error procesando evento '{request.event_type}': {exc}",
        )

    return AdminTestEventResponse(
        accepted=True,
        event_id=envelope.event_id,
        event_type=request.event_type,
        user_id=request.user_id,
    )
