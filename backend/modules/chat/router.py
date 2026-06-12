"""Chat REST API endpoints."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models.user import User
from app.dependencies import get_current_user
from modules.chat.schemas import (
    SendMessageRequest,
    SuggestReplyRequest,
    MessageResponse,
    SuggestReplyResponse,
)
from modules.chat import service
from common.errors import standard_response

router = APIRouter(prefix="/chats", tags=["chat"])


@router.get("/{match_id}/messages")
async def get_messages(
    match_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=100),
    before_id: uuid.UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    messages = await service.get_messages(db, user.id, match_id, limit, before_id)
    return standard_response(data=[MessageResponse.model_validate(m) for m in messages])


@router.post("/{match_id}/messages")
async def send_message(
    match_id: uuid.UUID,
    data: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    msg = await service.send_message(db, user.id, match_id, data.content, data.message_type)
    return standard_response(data=MessageResponse.model_validate(msg))


@router.post("/{match_id}/suggest-reply")
async def suggest_reply(
    match_id: uuid.UUID,
    data: SuggestReplyRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    tone = data.tone if data else "natural"
    msg_id = data.message_id if data else None
    suggestions = await service.suggest_reply(db, user.id, match_id, tone, msg_id)
    return standard_response(data=SuggestReplyResponse(suggestions=suggestions))
