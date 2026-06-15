import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models.user import User
from app.dependencies import get_current_user
from modules.assistant.schemas import (
    CreateSessionRequest,
    ChatRequest,
    SessionResponse,
    MessageResponse,
    ChatResponse,
)
from modules.assistant import service
from common.errors import standard_response

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.post("/sessions")
async def create_session(
    data: CreateSessionRequest | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    title = data.title if data else None
    session = await service.create_session(db, user.id, title)
    return standard_response(data=SessionResponse.model_validate(session))


@router.get("/sessions")
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    sessions = await service.list_sessions(db, user.id)
    return standard_response(data=[SessionResponse.model_validate(s) for s in sessions])


@router.get("/sessions/{session_id}/messages")
async def get_messages(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    messages = await service.get_messages(db, session_id, user.id)
    return standard_response(data=[MessageResponse.model_validate(m) for m in messages])


@router.post("/chat")
async def chat(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await service.chat(db, user.id, data)
    return standard_response(data=result)


@router.post("/sessions/{session_id}/mark-read")
async def mark_session_read(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Mark all assistant messages in a session as read."""
    count = await service.mark_messages_read(db, user.id, session_id)
    return standard_response(data={"marked": count})


@router.get("/unread-count")
async def unread_assistant_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get count of unread assistant messages across all sessions."""
    count = await service.get_unread_count(db, user.id)
    return standard_response(data={"unread_count": count})
