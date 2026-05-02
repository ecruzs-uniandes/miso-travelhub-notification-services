import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.database import get_db
from app.models.notification import Notification
from app.models.preference import NotificationPreference
from app.schemas.notification import NotificationListResponse, NotificationOut
from app.schemas.preference import PreferenceOut, PreferenceUpdate
from app.services.preference_service import PreferenceService

router = APIRouter(tags=["notifications"])


@router.get("/notifications", response_model=NotificationListResponse)
async def list_notifications(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Notification).where(Notification.user_id == current_user.user_id)
    count_query = select(func.count()).select_from(Notification).where(
        Notification.user_id == current_user.user_id
    )

    if unread_only:
        query = query.where(Notification.read_at.is_(None))
        count_query = count_query.where(Notification.read_at.is_(None))

    query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)

    total_result = await db.execute(count_query)
    total = total_result.scalar_one()

    result = await db.execute(query)
    notifications = result.scalars().all()

    items = [
        NotificationOut(
            id=n.id,
            event_type=n.event_type,
            title=n.title,
            body=n.body,
            metadata=n.metadata_,
            read_at=n.read_at,
            created_at=n.created_at,
        )
        for n in notifications
    ]

    return NotificationListResponse(items=items, total=total, limit=limit, offset=offset)


@router.post("/notifications/{notification_id}/read")
async def mark_as_read(
    notification_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.user_id,
        )
    )
    notification = result.scalar_one_or_none()

    if not notification:
        raise HTTPException(status_code=404, detail="Notificación no encontrada")

    if not notification.read_at:
        notification.read_at = datetime.now(timezone.utc)

    return {"id": str(notification_id), "read_at": notification.read_at}


@router.post("/notifications/read-all")
async def mark_all_read(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.user_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=now)
    )
    return {"status": "ok", "read_at": now}


@router.get("/notifications/preferences", response_model=PreferenceOut)
async def get_preferences(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PreferenceService(db)
    pref = await service.get_or_create(current_user.user_id)
    return pref


@router.put("/notifications/preferences", response_model=PreferenceOut)
async def update_preferences(
    body: PreferenceUpdate,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = PreferenceService(db)
    pref = await service.update(current_user.user_id, body)
    return pref
