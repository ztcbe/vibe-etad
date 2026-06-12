"""Matching API endpoints."""
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_session
from db.models.user import User
from app.dependencies import get_current_user
from modules.matching.schemas import SearchRequest
from modules.matching import service
from common.errors import standard_response

router = APIRouter(prefix="/matches", tags=["matching"])


@router.post("/search")
async def search_candidates(
    data: SearchRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    cards = await service.search_candidates(db, user.id, data.limit, data.filters)
    return standard_response(data=cards)


@router.get("/recommendations")
async def get_recommendations(
    limit: int = Query(default=5, ge=1, le=10),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    cards = await service.search_candidates(db, user.id, limit)
    return standard_response(data=cards)


@router.post("/{candidate_user_id}/like")
async def like_candidate(
    candidate_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await service.like_candidate(db, user.id, candidate_user_id)
    return standard_response(data=result)


@router.post("/{candidate_user_id}/pass")
async def pass_candidate(
    candidate_user_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    await service.pass_candidate(db, user.id, candidate_user_id)
    return standard_response(data={"status": "passed"})


@router.get("")
async def list_matches(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    result = await service.list_matches(db, user.id)
    return standard_response(data=result)


@router.get("/{match_id}")
async def get_match_detail(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """Get match detail — returns the candidate's public profile + match info."""
    from db.models.matching import Match
    from db.models.profile import UserProfile
    from sqlalchemy import select, or_

    match = await db.get(Match, match_id)
    if match is None or (match.user_a_id != user.id and match.user_b_id != user.id):
        from common.errors import NotFoundError
        raise NotFoundError(code="MATCH_NOT_FOUND", message="Match not found")

    other_id = match.user_b_id if match.user_a_id == user.id else match.user_a_id
    other_user = await db.get(User, other_id)
    other_profile = (await db.execute(
        select(UserProfile).where(UserProfile.user_id == other_id)
    )).scalar_one_or_none()

    from modules.profiles.schemas import PublicProfileResponse
    from modules.profiles.service import _calculate_age

    profile_data = PublicProfileResponse(
        user_id=other_id,
        display_name=other_profile.display_name if other_profile else None,
        age=_calculate_age(other_user.date_of_birth) if other_user else None,
        city=other_profile.city if other_profile else None,
        avatar_url=other_profile.avatar_url if other_profile else None,
        public_summary=other_profile.public_summary if other_profile else None,
        dating_goal=other_profile.dating_goal.value if other_profile and other_profile.dating_goal else None,
        top_hobbies=(other_profile.hobbies if other_profile and isinstance(other_profile.hobbies, list) else []),
    )

    return standard_response(data={
        "match_id": match.id,
        "status": match.status.value,
        "matched_at": match.created_at.isoformat(),
        "profile": profile_data.model_dump(),
    })


@router.post("/{match_id}/unmatch")
async def unmatch(
    match_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    await service.unmatch(db, user.id, match_id)
    return standard_response(data={"status": "unmatched"})
