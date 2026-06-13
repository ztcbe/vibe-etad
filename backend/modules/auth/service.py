import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User
from db.models.profile import UserProfile
from modules.auth.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from modules.auth.schemas import RegisterRequest, TokenResponse
from common.errors import ConflictError, UnauthorizedError, ValidationError, AppError
from common.enums import UserStatus, UserRole

# In-memory token blacklist (MVP — use Redis/DB for production)
_revoked_tokens: set[str] = set()


async def register(db: AsyncSession, data: RegisterRequest) -> TokenResponse:
    if data.password != data.confirm_password:
        raise ValidationError(message="Passwords do not match", details={"field": "confirm_password"})

    # Username uniqueness
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise ConflictError(code="USERNAME_EXISTS", message="Username already taken")

    user = User(
        username=data.username,
        password_hash=hash_password(data.password),
        date_of_birth=data.date_of_birth,
        is_age_verified=True,
    )
    db.add(user)
    await db.flush()

    profile = UserProfile(user_id=user.id, completeness_score=0)
    db.add(profile)
    await db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


async def login(db: AsyncSession, username: str, password: str) -> TokenResponse:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise UnauthorizedError(code="INVALID_CREDENTIALS", message="Invalid username or password")
    if user.status == UserStatus.DISABLED:
        raise UnauthorizedError(code="ACCOUNT_DISABLED", message="Account has been disabled")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


async def refresh(db: AsyncSession, refresh_token: str) -> TokenResponse:
    if refresh_token in _revoked_tokens:
        raise UnauthorizedError(message="Token has been revoked")

    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise UnauthorizedError(message="Invalid refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or user.status == UserStatus.DISABLED:
        raise UnauthorizedError(message="User not found or disabled")

    # Revoke old refresh token (rotation)
    _revoked_tokens.add(refresh_token)

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


async def logout(refresh_token: str) -> None:
    _revoked_tokens.add(refresh_token)
