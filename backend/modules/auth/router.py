from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models.user import User
from app.dependencies import get_current_user
from modules.auth.schemas import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, UserMeResponse
from modules.auth import service
from common.errors import standard_response

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_session)):
    tokens = await service.register(db, data)
    return standard_response(data=tokens)


@router.post("/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_session)):
    tokens = await service.login(db, data.username, data.password)
    return standard_response(data=tokens)


@router.post("/refresh")
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_session)):
    tokens = await service.refresh(db, data.refresh_token)
    return standard_response(data=tokens)


@router.post("/logout")
async def logout(data: RefreshRequest):
    await service.logout(data.refresh_token)
    return standard_response(data={"message": "Logged out"})


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    profile = user.profile
    return standard_response(data=UserMeResponse(
        id=user.id,
        username=user.username,
        display_name=profile.display_name if profile else None,
        role=user.role.value,
        status=user.status.value,
        date_of_birth=user.date_of_birth,
        is_age_verified=user.is_age_verified,
        completeness_score=profile.completeness_score if profile else 0,
        avatar_url=profile.avatar_url if profile else None,
        created_at=user.created_at,
    ))
