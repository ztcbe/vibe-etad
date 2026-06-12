import uuid
from datetime import date

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.user import User
from db.models.profile import UserProfile
from db.models.moderation import Block
from modules.profiles.schemas import ProfileUpdateRequest, CompletenessResponse, CompletenessBreakdown, PublicProfileResponse
from common.errors import NotFoundError, ValidationError
from common.enums import VisibilityStatus, DatingGoal


# Fields that affect matching — require embedding rebuild
MATCHING_FIELDS = {"dating_goal", "personality_traits", "hobbies", "values", "preferences", "deal_breakers", "city", "lat", "lng", "bio"}


async def get_my_profile(db: AsyncSession, user_id: uuid.UUID) -> UserProfile:
    result = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise NotFoundError(code="PROFILE_NOT_FOUND", message="Profile not found")
    return profile


async def update_my_profile(db: AsyncSession, user_id: uuid.UUID, data: ProfileUpdateRequest) -> UserProfile:
    profile = await get_my_profile(db, user_id)
    update_data = data.model_dump(exclude_none=True)

    needs_embedding_rebuild = False
    for field, value in update_data.items():
        if field == "dating_goal" and value is not None:
            try:
                value = DatingGoal(value)
            except ValueError:
                raise ValidationError(message=f"Invalid dating_goal: {value}")
        if field == "visibility_status" and value is not None:
            try:
                value = VisibilityStatus(value)
            except ValueError:
                raise ValidationError(message=f"Invalid visibility_status: {value}")
        setattr(profile, field, value)
        if field in MATCHING_FIELDS:
            needs_embedding_rebuild = True

    # Recalculate completeness
    profile.completeness_score = _calculate_completeness_score(profile)

    await db.commit()
    await db.refresh(profile)

    # TODO: trigger embedding rebuild if needs_embedding_rebuild (S2+)
    return profile


async def get_public_profile(db: AsyncSession, viewer_user_id: uuid.UUID, target_user_id: uuid.UUID) -> PublicProfileResponse:
    # Check if target exists and is visible
    result = await db.execute(
        select(User, UserProfile)
        .join(UserProfile, UserProfile.user_id == User.id)
        .where(User.id == target_user_id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotFoundError(code="PROFILE_NOT_AVAILABLE", message="Profile not available")

    user, profile = row

    # Check blocks (both directions)
    block_result = await db.execute(
        select(Block).where(
            or_(
                (Block.blocker_user_id == viewer_user_id) & (Block.blocked_user_id == target_user_id),
                (Block.blocker_user_id == target_user_id) & (Block.blocked_user_id == viewer_user_id),
            )
        )
    )
    if block_result.scalar_one_or_none():
        raise NotFoundError(code="PROFILE_NOT_AVAILABLE", message="Profile not available")

    # Check visibility
    if profile.visibility_status != VisibilityStatus.ACTIVE:
        raise NotFoundError(code="PROFILE_NOT_AVAILABLE", message="Profile not available")

    # Calculate age
    today = date.today()
    age = today.year - user.date_of_birth.year - ((today.month, today.day) < (user.date_of_birth.month, user.date_of_birth.day))

    # Extract top hobbies from JSONB
    hobbies = profile.hobbies or {}
    if isinstance(hobbies, list):
        top_hobbies = hobbies[:5]
    elif isinstance(hobbies, dict):
        top_hobbies = list(hobbies.keys())[:5]
    else:
        top_hobbies = []

    return PublicProfileResponse(
        user_id=user.id,
        display_name=profile.display_name,
        age=age,
        city=profile.city,
        avatar_url=profile.avatar_url,
        public_summary=profile.public_summary,
        dating_goal=profile.dating_goal.value if profile.dating_goal else None,
        top_hobbies=top_hobbies,
    )


async def get_completeness(db: AsyncSession, user_id: uuid.UUID) -> CompletenessResponse:
    profile = await get_my_profile(db, user_id)
    score, breakdown, missing = _calculate_completeness(profile)
    return CompletenessResponse(
        completeness_score=score,
        breakdown=breakdown,
        missing_fields=missing,
    )


def _calculate_completeness_score(profile: UserProfile) -> int:
    score, _, _ = _calculate_completeness(profile)
    return score


def _calculate_completeness(profile: UserProfile) -> tuple[int, CompletenessBreakdown, list[str]]:
    missing: list[str] = []

    # basic_info: 30
    basic_score = 0
    if profile.display_name:
        basic_score += 6
    else:
        missing.append("display_name")
    # date_of_birth is on User model, checked via user relationship
    basic_score += 6  # always has date_of_birth (required on user)
    if profile.gender:
        basic_score += 6
    else:
        missing.append("gender")
    if profile.interested_in:
        basic_score += 6
    else:
        missing.append("interested_in")
    if profile.city:
        basic_score += 6
    else:
        missing.append("city")

    # dating_goal: 15
    goal_score = 15 if profile.dating_goal else 0
    if not profile.dating_goal:
        missing.append("dating_goal")

    # personality_hobbies: 20
    ph_score = 0
    hobbies = profile.hobbies or {}
    hobbies_list = hobbies if isinstance(hobbies, list) else list(hobbies.keys()) if isinstance(hobbies, dict) else []
    traits = profile.personality_traits or {}
    traits_list = traits if isinstance(traits, list) else list(traits.keys()) if isinstance(traits, dict) else []

    if len(traits_list) > 0:
        ph_score += 10
    else:
        missing.append("personality_traits")
    if len(hobbies_list) >= 3:
        ph_score += 10
    elif len(hobbies_list) > 0:
        ph_score += 5
        missing.append("hobbies_min_3")
    else:
        missing.append("hobbies_min_3")

    # preferences: 20
    pref_score = 0
    prefs = profile.preferences or {}
    if prefs.get("preferred_age_min") is not None and prefs.get("preferred_age_max") is not None:
        pref_score += 7
    else:
        missing.append("preferred_age_range")
    if prefs.get("preferred_distance_km") is not None:
        pref_score += 7
    else:
        missing.append("preferred_distance_km")
    if prefs.get("preferred_gender"):
        pref_score += 6
    else:
        missing.append("preferred_gender")

    # bio_summary: 15
    bio_score = 15 if profile.public_summary else 0
    if not profile.public_summary:
        missing.append("public_summary")

    breakdown = CompletenessBreakdown(
        basic_info={"score": basic_score, "max": 30},
        dating_goal={"score": goal_score, "max": 15},
        personality_hobbies={"score": ph_score, "max": 20},
        preferences={"score": pref_score, "max": 20},
        bio_summary={"score": bio_score, "max": 15},
    )

    total = basic_score + goal_score + ph_score + pref_score + bio_score
    return total, breakdown, missing
