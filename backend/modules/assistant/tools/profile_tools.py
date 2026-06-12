"""Profile tools for the AI assistant — reads DB/user from contextvars."""
import json
import uuid

from modules.assistant.tools import current_db, current_user_id
from modules.profiles import service as profile_service
from modules.profiles.schemas import ProfileUpdateRequest


async def get_my_profile() -> dict:
    """Get the current user's full dating profile. Returns all fields."""
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    profile = await profile_service.get_my_profile(db, uuid.UUID(user_id_str))
    prefs = profile.preferences or {}
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except (json.JSONDecodeError, TypeError):
            prefs = {}

    return {
        "display_name": profile.display_name,
        "gender": profile.gender,
        "interested_in": profile.interested_in,
        "city": profile.city,
        "dating_goal": profile.dating_goal.value if profile.dating_goal else None,
        "bio": profile.bio,
        "personality_traits": profile.personality_traits,
        "hobbies": profile.hobbies,
        "values": profile.values,
        "communication_style": profile.communication_style,
        "deal_breakers": profile.deal_breakers,
        "preferences": prefs,
        "public_summary": profile.public_summary,
        "completeness_score": profile.completeness_score,
        "visibility_status": profile.visibility_status.value if profile.visibility_status else None,
    }


async def calculate_profile_completeness() -> dict:
    """Calculate how complete the user's profile is.

    Returns completeness_score (0-100), breakdown by category, and list of missing_fields.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    result = await profile_service.get_completeness(db, uuid.UUID(user_id_str))
    return {
        "completeness_score": result.completeness_score,
        "breakdown": {
            "basic_info": result.breakdown.basic_info,
            "dating_goal": result.breakdown.dating_goal,
            "personality_hobbies": result.breakdown.personality_hobbies,
            "preferences": result.breakdown.preferences,
            "bio_summary": result.breakdown.bio_summary,
        },
        "missing_fields": result.missing_fields,
    }


async def update_my_profile(
    display_name: str | None = None,
    gender: str | None = None,
    interested_in: str | None = None,
    city: str | None = None,
    dating_goal: str | None = None,
    bio: str | None = None,
    personality_traits: list | None = None,
    hobbies: list | None = None,
    values: list | None = None,
    communication_style: str | None = None,
    deal_breakers: list | None = None,
    preferences: dict | None = None,
    public_summary: str | None = None,
) -> dict:
    """Update the user's profile with new information. Only provide fields that changed.

    Args:
        display_name: How the user wants to be called.
        gender: User's gender.
        interested_in: Gender(s) the user is interested in.
        city: Current city.
        dating_goal: One of serious, casual, friends_first, not_sure.
        bio: Free-text bio.
        personality_traits: List of personality traits (e.g. ["thân thiện", "hài hước"]).
        hobbies: List of hobbies (e.g. ["Cà phê", "Đọc sách", "Trekking"]).
        values: List of values.
        communication_style: Communication style description.
        deal_breakers: List of deal-breaker items.
        preferences: Dict with preferred_age_min, preferred_age_max, preferred_distance_km, preferred_gender.
        public_summary: A short public-facing summary for the profile card.
    """
    db = current_db.get()
    user_id_str = current_user_id.get()
    if not db or not user_id_str:
        return {"error": "No session context available"}

    update_data = {}
    if display_name is not None:
        update_data["display_name"] = display_name
    if gender is not None:
        update_data["gender"] = gender
    if interested_in is not None:
        update_data["interested_in"] = interested_in
    if city is not None:
        update_data["city"] = city
    if dating_goal is not None:
        update_data["dating_goal"] = dating_goal
    if bio is not None:
        update_data["bio"] = bio
    if personality_traits is not None:
        update_data["personality_traits"] = personality_traits
    if hobbies is not None:
        update_data["hobbies"] = hobbies
    if values is not None:
        update_data["values"] = values
    if communication_style is not None:
        update_data["communication_style"] = communication_style
    if deal_breakers is not None:
        update_data["deal_breakers"] = deal_breakers
    if preferences is not None:
        update_data["preferences"] = preferences
    if public_summary is not None:
        update_data["public_summary"] = public_summary

    if not update_data:
        return {"message": "Không có thông tin nào được cập nhật.", "updated_fields": []}

    request = ProfileUpdateRequest(**update_data)
    profile = await profile_service.update_my_profile(db, uuid.UUID(user_id_str), request)

    # Recalculate completeness after update
    completeness = await profile_service.get_completeness(db, uuid.UUID(user_id_str))

    return {
        "message": f"Đã cập nhật: {', '.join(update_data.keys())}",
        "updated_fields": list(update_data.keys()),
        "new_completeness_score": completeness.completeness_score,
        "missing_fields": completeness.missing_fields,
    }
