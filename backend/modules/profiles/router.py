import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models.user import User
from app.dependencies import get_current_user
from modules.profiles.schemas import ProfileUpdateRequest, ProfileResponse, CompletenessResponse, PublicProfileResponse
from modules.profiles import service
from common.errors import standard_response

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me")
async def get_my_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    profile = await service.get_my_profile(db, user.id)
    return standard_response(data=ProfileResponse.model_validate(profile))


@router.patch("/me")
async def update_my_profile(
    data: ProfileUpdateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    profile = await service.update_my_profile(db, user.id, data)
    return standard_response(data=ProfileResponse.model_validate(profile))


@router.get("/me/completeness")
async def get_completeness(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await service.get_completeness(db, user.id)
    return standard_response(data=result)


@router.get("/{user_id}")
async def get_public_profile(
    user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await service.get_public_profile(db, user.id, user_id)
    return standard_response(data=result)
