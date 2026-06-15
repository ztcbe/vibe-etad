"""Notification REST API endpoints."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models.user import User
from app.dependencies import get_current_user, get_current_admin
from modules.notifications import service
from modules.notifications.schemas import (
    ManualNotifyRequest,
    MarkReadRequest,
)
from common.enums import NotificationType
from common.errors import standard_response

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await service.list_notifications(db, user.id, limit, offset, unread_only)
    return standard_response(data=result)


@router.get("/unread-count")
async def unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await service.get_unread_count(db, user.id)
    return standard_response(data=result.model_dump())


@router.post("/mark-read")
async def mark_read(
    data: MarkReadRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    count = await service.mark_read(db, user.id, data.notification_ids)
    return standard_response(data={"marked": count})


@router.post("/manual")
async def manual_notify(
    data: ManualNotifyRequest,
    admin: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_session),
):
    try:
        notif_type = NotificationType(data.type)
    except ValueError:
        notif_type = NotificationType.SYSTEM

    notif = await service.create_notification(
        db=db,
        user_id=data.user_id,
        type=notif_type,
        title=data.title,
        body=data.body,
        is_one_shot=False,
        extra_data=data.extra_data,
    )
    return standard_response(data={"id": str(notif.id), "created": notif is not None})
