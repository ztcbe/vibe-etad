import uuid
from datetime import datetime, timezone

from fastapi import Depends, Query, WebSocket, WebSocketException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from db.session import get_session
from db.models.user import User
from db.models.profile import UserProfile
from modules.auth.security import decode_token
from common.errors import UnauthorizedError, ForbiddenError
from common.enums import UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> User:
    payload = decode_token(token)
    if payload is None:
        raise UnauthorizedError(message="Invalid or expired token")
    user_id = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError(message="Invalid token payload")
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError(message="User not found")

    # Update last_active_at (throttled: only if > 60s since last update)
    now = datetime.now(timezone.utc)
    if user.last_active_at is None or (now - user.last_active_at).total_seconds() > 60:
        user.last_active_at = now
        await db.commit()

    return user


async def get_current_admin(
    user: User = Depends(get_current_user),
) -> User:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError(message="Admin access required")
    return user


async def get_current_user_ws(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_session),
) -> User:
    """Authenticate WebSocket connection via JWT token in query string."""
    payload = decode_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketException(code=4001, reason="Invalid token")
    user_id = payload.get("sub")
    if user_id is None:
        await websocket.close(code=4001, reason="Invalid token")
        raise WebSocketException(code=4001, reason="Invalid token")
    result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == uuid.UUID(user_id))
    )
    user = result.scalar_one_or_none()
    if user is None:
        await websocket.close(code=4001, reason="User not found")
        raise WebSocketException(code=4001, reason="User not found")

    # Update last_active_at (throttled: only if > 60s since last update)
    now = datetime.now(timezone.utc)
    if user.last_active_at is None or (now - user.last_active_at).total_seconds() > 60:
        user.last_active_at = now
        await db.commit()

    return user
